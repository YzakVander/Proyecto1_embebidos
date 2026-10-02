"""Orquestador del sistema de control de acceso.

Arquitectura de hilos (H1)
--------------------------
  1. Hilo de GStreamer      - captura, codifica, transmite, graba.
                              Nunca espera a nadie.
  2. Hilo de eventos        - lee las decisiones del vigilante desde el FIFO.
  3. Hilo por solicitud     - espera la decision con su plazo (H2) y escribe
                              el clip. Al desprenderse del hilo de eventos,
                              varias solicitudes pueden convivir.
  4. Hilo de reconexion     - E3: reintenta levantar la tuberia tras una falla.
  5. Hilos de red           - CU-3: uno por puesto de vigilancia conectado por
                              TCP (red.py). Usan el mismo procesador de
                              comandos que el FIFO.

El callback del appsink (hilo 1) solo copia bytes a la deque y retorna: B5.
Toda escritura a disco ocurre en el hilo 3.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time

from gi.repository import GLib

from .actuador import IndicadoresAcceso
from .buffer_circular import BufferCircular, escribir_clip_anexo, escribir_clip_mp4
from .config import Config
from .credencial import generar_credencial, verificar
from .lector_qr import LectorQR
from .registro import RegistroCredenciales, Rol
from .decision import Bitacora, RegistroAcceso, Resultado, SolicitudAcceso, ahora_iso
from .pipeline import PipelineAcceso
from .red import ServidorDecisiones
from .retencion import Carpeta, Retencion, clave_evento, clave_segmento, verificar_corruptos

log = logging.getLogger(__name__)


class ServicioAcceso:
    def __init__(self, cfg: Config) -> None: #Constructor de la clase.
        self._cfg = cfg #Copia el argumento a un atributo _cfg
        # El buffer debe alcanzar para la ventana COMPLETA del clip:
        # los segundos previos al evento mas los posteriores. Dimensionarlo
        # solo con segundos_antes hace que al pedir la instantanea la parte
        # mas vieja ya se haya descartado y el clip quede corto.

        #-----> Por aqui freno: voy a revisar buffer_circular.py
        self._buffer = BufferCircular(
            segundos=cfg.clips.segundos_antes + cfg.clips.segundos_despues,
            fps=cfg.codec.fps,
            max_buffers=cfg.clips.max_buffers,
        )
        # CU-11/CU-12: credenciales registradas
        self._registro = RegistroCredenciales(cfg.credenciales.ruta)
        # Serializa la escritura de imagenes de credenciales: un ALTA no puede
        # generar su imagen mientras REGENERAR_QR esta vaciando la carpeta.
        self._lock_imagenes = threading.Lock()

        # CU-13: el lector se construye ANTES que el pipeline, que
        # consulta si debe agregar la rama de cuadros crudos.
        self._lector: LectorQR | None = None
        if cfg.qr.habilitado:
            self._lector = LectorQR(
                self._al_detectar_qr,
                enfriamiento_s=cfg.qr.enfriamiento_s,
                periodo_s=1.0 / max(cfg.qr.analisis_por_s, 0.1),
                ancho_analisis=cfg.qr.ancho_analisis,
            )

        self._pipeline = PipelineAcceso(cfg, self._buffer, self._lector)

        # RF-7: retencion con un tope independiente por carpeta
        self._carpetas_evidencia: list[str] = []
        carpetas: list[Carpeta] = []
        g, c = cfg.grabacion, cfg.clips
        if g.habilitada:
            self._carpetas_evidencia.append(g.directorio)
            carpetas.append(Carpeta("evidencia", g.directorio, g.max_megabytes * 1024 * 1024,
                                    clave_segmento(g.patron.split("%")[0])))
        if c.habilitados:
            self._carpetas_evidencia.append(c.directorio)
            carpetas.append(Carpeta("eventos", c.directorio, c.max_megabytes * 1024 * 1024,
                                    clave_evento))
        self._retencion = Retencion(
            carpetas, en_uso=lambda: {self._pipeline.segmento_actual})

        self._indicadores = IndicadoresAcceso(cfg.actuador)
        self._bitacora = Bitacora(cfg.bitacora.ruta)

        self._bucle = GLib.MainLoop()

        self._pendiente: SolicitudAcceso | None = None
        self._lock_pendiente = threading.Lock()
        self._parar = threading.Event()
        self._contador = 0
        self._reconectando = threading.Event()

        # CU-3: canal de red para el puesto de vigilancia (otra computadora).
        # Recibe los mismos comandos que el FIFO; origen="red" permite
        # rechazar los que no deben llegar por red (SALIR).
        self._red: ServidorDecisiones | None = None
        if cfg.eventos.red_habilitada:
            self._red = ServidorDecisiones(
                cfg.eventos.red_puerto,
                lambda texto: self._procesar_comando(texto, origen="red"),
                cfg.eventos.red_clientes,
                al_conectar=self._al_conectar_vigilante,
            )

    # ------------------------------------------------------------------ #
    def ejecutar(self, dot_dir: str | None = None) -> int:
        # Antes de montar la tuberia: borrar los clips que quedaron corruptos
        # (sin indice) por un corte de energia, un cierre forzado o una falla
        # de la camara. Aun no hay ningun archivo abierto, asi que es seguro.
        verificar_corruptos(self._carpetas_evidencia)

        self._pipeline.al_fallar(self._al_fallar_pipeline)
        self._pipeline.al_cerrar_segmento(self._retencion.solicitar)
        self._retencion.iniciar()
        self._pipeline.construir()
        self._pipeline.iniciar()

        if self._lector is not None:
            self._lector.iniciar()

        if dot_dir:
            GLib.timeout_add_seconds(3, self._volcar_dot, dot_dir)

        threading.Thread(target=self._escuchar_eventos, daemon=True).start()
        if self._red is not None:
            self._red.iniciar()

        for sig in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, self._al_senal)

        log.info("servicio de control de acceso en operacion")
        try:
            self._bucle.run()
        finally:
            self._apagar()
        return 0

    # ------------------------------------------------------------------ #
    # Entrada de eventos: FIFO o teclado
    # ------------------------------------------------------------------ #
    def _escuchar_eventos(self) -> None:
        cfg = self._cfg.eventos
        if cfg.fuente == "teclado":
            self._escuchar_teclado()
            return

        ruta = cfg.fifo
        directorio = os.path.dirname(ruta)
        if directorio:
            os.makedirs(directorio, exist_ok=True)
        if not os.path.exists(ruta):
            os.mkfifo(ruta, 0o660)

        log.info("eventos por FIFO: %s", ruta)
        log.info("  solicitud : echo 'SOLICITUD ID-001' > %s", ruta)
        log.info("  permitir  : echo 'PERMITIR'        > %s", ruta)
        log.info("  denegar   : echo 'DENEGAR'         > %s", ruta)

        while not self._parar.is_set():
            try:
                with open(ruta, "r") as fifo:
                    for linea in fifo:
                        if self._parar.is_set():
                            return
                        self._procesar_comando(linea.strip())
            except OSError as exc:
                log.error("error leyendo FIFO: %s", exc)
                time.sleep(1.0)

    def _escuchar_teclado(self) -> None:
        import sys
        log.info("eventos por teclado: SOLICITUD <id> | PERMITIR | DENEGAR | SALIR")
        while not self._parar.is_set():
            linea = sys.stdin.readline()
            if not linea:
                break
            self._procesar_comando(linea.strip())

    def _procesar_comando(self, texto: str, origen: str = "local") -> tuple[bool, str]:
        """Interpreta un comando del FIFO, del teclado o de la red.

        Devuelve (exito, mensaje). El FIFO y el teclado ignoran el retorno;
        el canal de red se lo envia al vigilante como 'OK ...' o 'ERROR ...'.
        """
        if not texto:
            return False, "comando vacio"
        partes = texto.split(maxsplit=1)
        verbo = partes[0].upper()

        if verbo == "SOLICITUD":
            # Sin identificador, la placa lo genera con la fecha y hora de
            # apertura: es unico aunque el servicio se reinicie.
            ident = partes[1] if len(partes) > 1 else time.strftime("S-%Y%m%d-%H%M%S")
            return self._nueva_solicitud(ident)
        if verbo in ("PERMITIR", "DENEGAR"):
            return self._resolver(verbo == "PERMITIR")
        if verbo == "ALTA":
            return self._alta(partes[1] if len(partes) > 1 else "")
        if verbo == "BAJA":
            return self._baja(partes[1] if len(partes) > 1 else "")
        if verbo == "LISTAR":
            return True, self._registro.resumen()
        if verbo == "REGENERAR_QR":
            return self._regenerar_qr()
        if verbo == "BORRAR_CREDENCIALES":
            return self._borrar_credenciales(partes[1] if len(partes) > 1 else "")
        if verbo == "ESTADO":
            return True, self._estado()
        if verbo == "PING":
            return True, "PONG"   # no toca nada; sirve para medir el RTT (RF-3)
        if verbo == "SALIR":
            if origen == "red":
                # Nadie en la red deberia poder apagar el control de acceso
                return False, "SALIR no se permite por red"
            self._bucle.quit()
            return True, "apagando"

        log.warning("comando no reconocido: %s", texto)
        return False, f"comando no reconocido: {texto}"

    def _estado(self) -> str:
        with self._lock_pendiente:
            solicitud = self._pendiente
        if solicitud is None:
            return "sin solicitud pendiente"
        return (f"pendiente {solicitud.identificador} "
                f"restan {solicitud.restante_s():.0f} s")

    def _difundir(self, texto: str) -> None:
        """Aviso 'EVENTO ...' a los puestos de vigilancia conectados."""
        if self._red is not None:
            self._red.difundir(texto)

    # ------------------------------------------------------------------ #
    # CU-3: procesamiento de la solicitud
    # ------------------------------------------------------------------ #
    def _nueva_solicitud(self, identificador: str) -> tuple[bool, str]:
        with self._lock_pendiente:
            if self._pendiente is not None:
                log.warning("ya hay una solicitud en curso; se ignora '%s'",
                            identificador)
                return False, ("ya hay una solicitud en curso "
                               f"({self._pendiente.identificador})")
            self._contador += 1
            solicitud = SolicitudAcceso(
                identificador, self._cfg.eventos.timeout_decision_s
            )
            self._pendiente = solicitud

        plazo = self._cfg.eventos.timeout_decision_s
        log.info("=== SOLICITUD #%d: %s (plazo %.0f s) ===",
                 self._contador, identificador, plazo)
        threading.Thread(
            target=self._atender, args=(solicitud,), daemon=True
        ).start()
        self._difundir(f"SOLICITUD {identificador} plazo={plazo:.0f}s")
        return True, f"solicitud {identificador} abierta, plazo {plazo:.0f} s"

    def _resolver(self, permitido: bool) -> tuple[bool, str]:
        # Resolver y liberar ocurren juntos, dentro del mismo candado: cuando
        # el vigilante recibe el OK, la solicitud ya no esta pendiente. Si la
        # liberacion quedara en manos del hilo de _atender, habria una ventana
        # de milisegundos (lo que tarda en despertar) en la que ESTADO diria
        # "pendiente" y una SOLICITUD nueva seria rechazada.
        with self._lock_pendiente:
            solicitud = self._pendiente
            cerrada = solicitud is not None and not solicitud.resolver(permitido)
            if solicitud is not None and not cerrada:
                self._pendiente = None
        if solicitud is None:
            log.warning("no hay solicitud pendiente que resolver")
            return False, "no hay solicitud pendiente"
        if cerrada:
            log.warning("la solicitud ya habia vencido")
            return False, f"la solicitud {solicitud.identificador} ya estaba cerrada"
        return True, f"{solicitud.identificador} {'PERMITIDO' if permitido else 'DENEGADO'}"

    def _atender(self, solicitud: SolicitudAcceso) -> None:
        """Hilo por solicitud: espera la decision, indica, anota y escribe el clip.

        El orden importa. En cuanto hay decision (o vence el plazo):
          1. Buzzer, consola y aviso al vigilante.
          2. Bitacora, con la hora EXACTA de la decision (RF-4). Si se anotara
             despues del clip, quedaria con segundos_despues de retraso y se
             perderia si el servicio se apaga mientras se espera el clip.
          3. La solicitud ya esta liberada (ver _resolver y el bloque de abajo):
             ESTADO deja de reportarla como pendiente y se acepta una
             SOLICITUD nueva de inmediato.
          4. Al final el clip, que tiene que esperar segundos_despues. Si en
             ese lapso se resuelve otra solicitud, los dos clips se escriben
             en paralelo sin problema: cada uno toma su propia copia del buffer.
        """
        inicio = time.monotonic()
        resultado = solicitud.esperar()          # H2: bloquea o vence
        latencia_ms = (time.monotonic() - inicio) * 1000.0
        instante = ahora_iso()                   # hora de la decision

        # Si fue el vigilante, _resolver ya libero la solicitud. Si vencio el
        # plazo, se libera aqui. Solo si la pendiente sigue siendo ESTA: pudo
        # haberse abierto otra nueva en cuanto _resolver libero la anterior.
        with self._lock_pendiente:
            if self._pendiente is solicitud:
                self._pendiente = None

        self._indicadores.indicar(resultado, solicitud.identificador)   # RF-5: buzzer + consola
        # Aviso inmediato al vigilante, sobre todo para el vencimiento: el
        # temporizador corre en la placa y el vigilante no lo veria de otra forma.
        self._difundir(f"RESULTADO {solicitud.identificador} {resultado.value}")

        # El nombre del clip se fija ya, con la hora de la decision, para
        # poder anotarlo en la bitacora antes de escribir el archivo.
        clip = None
        if self._cfg.clips.habilitados:
            clip = self._ruta_clip(solicitud.identificador)

        self._bitacora.anotar(RegistroAcceso(
            timestamp=instante,
            identificador=solicitud.identificador,
            resultado=resultado.value,
            latencia_decision_ms=round(latencia_ms, 1),
            clip=clip,
            nota=None if resultado != Resultado.VENCIDO else
                 "denegado automaticamente por vencimiento del plazo",
        ))

        if clip is not None:
            self._escribir_clip(clip)

    def _ruta_clip(self, identificador: str) -> str:
        """Ruta del clip de un evento, con la hora actual en el nombre."""
        seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in identificador)
        nombre = f"evento_{time.strftime('%Y%m%d-%H%M%S')}_{seguro}.mp4"
        return os.path.join(self._cfg.clips.directorio, nombre)

    def _escribir_clip(self, ruta: str) -> bool:
        """Clip de pre-evento + post-evento desde el buffer circular."""
        cfg = self._cfg.clips
        # Esperar los segundos posteriores para que el buffer los acumule.
        time.sleep(cfg.segundos_despues)

        ventana = cfg.segundos_antes + cfg.segundos_despues
        cuadros = self._buffer.instantanea(ventana)
        if not cuadros:
            # La bitacora ya tiene anotada esta ruta: se deja constancia aqui
            log.warning("buffer vacio; no se escribio el clip %s", ruta)
            return False

        try:
            escribir_clip_mp4(ruta, cuadros, self._cfg.codec.fps)
        except Exception as exc:                     # noqa: BLE001
            # Respaldo: no perder la evidencia. Se guarda el flujo crudo con
            # el mismo nombre base; la bitacora apunta al .mp4, por eso el
            # log deja claro donde quedo.
            if os.path.exists(ruta):
                os.remove(ruta)                      # MP4 a medias: inservible
            respaldo = os.path.splitext(ruta)[0] + ".h264"
            log.error("no se pudo empaquetar el clip en MP4 (%s); "
                      "se guarda crudo en %s", exc, respaldo)
            escribir_clip_anexo(respaldo, cuadros)
        self._retencion.solicitar()     # RF-7: el clip nuevo puede exceder el tope
        return True


    # ------------------------------------------------------------------ #
    # CU-11 / CU-12: gestion de credenciales por el vigilante
    # ------------------------------------------------------------------ #
    def _alta(self, argumentos: str) -> tuple[bool, str]:
        """ALTA <rol> <nombre completo>

        El rol va primero porque es una sola palabra: asi el nombre puede
        tener los espacios que haga falta sin necesitar comillas.
        """
        partes = argumentos.split(maxsplit=1)
        if len(partes) < 2:
            return False, ("uso: ALTA <rol> <nombre>   roles: "
                           + ", ".join(r.value for r in Rol))
        rol, nombre = partes[0], partes[1]

        try:
            cred = self._registro.alta(nombre, rol)
        except ValueError as exc:
            return False, str(exc)

        # La credencial se genera y se VERIFICA: una que no se puede leer es
        # peor que no tenerla, porque el fallo aparece recien cuando la
        # persona esta en la puerta.
        ruta = self._ruta_imagen(cred.identificador)
        try:
            with self._lock_imagenes:
                generar_credencial(ruta, cred.identificador, cred.nombre, cred.rol)
                legible = verificar(ruta, cred.identificador)
            if not legible:
                return False, (f"{cred.identificador} registrado, pero la "
                               "credencial generada no se decodifica")
        except Exception as exc:                      # noqa: BLE001
            log.error("no se pudo generar la credencial: %s", exc)
            return True, (f"{cred.identificador} registrado, pero fallo la "
                          f"generacion de la imagen: {exc}")

        self._difundir(f"ALTA {cred.identificador} {cred.rol} {cred.nombre}")
        return True, (f"{cred.identificador} | {cred.nombre} | {cred.rol} | "
                      f"credencial en {ruta}")

    def _baja(self, argumentos: str) -> tuple[bool, str]:
        """BAJA <identificador> [motivo]"""
        partes = argumentos.split(maxsplit=1)
        if not partes:
            return False, "uso: BAJA <identificador> [motivo]"
        ident = partes[0]
        motivo = partes[1] if len(partes) > 1 else None

        try:
            cred = self._registro.baja(ident, motivo)
        except ValueError as exc:
            return False, str(exc)

        self._difundir(f"BAJA {cred.identificador} {cred.nombre}")
        return True, f"acceso revocado: {cred.identificador} | {cred.nombre}"

    _EXT_IMAGEN = (".bmp", ".png", ".jpg", ".jpeg")

    def _ruta_imagen(self, identificador: str) -> str:
        return os.path.join(self._cfg.credenciales.directorio, f"{identificador}.bmp")

    def _borrar_imagenes(self) -> int:
        """Borra las imagenes de credenciales. Llamar con _lock_imagenes tomado."""
        directorio = self._cfg.credenciales.directorio
        os.makedirs(directorio, exist_ok=True)
        borradas = 0
        for nombre in os.listdir(directorio):
            ruta = os.path.join(directorio, nombre)
            if os.path.isfile(ruta) and nombre.lower().endswith(self._EXT_IMAGEN):
                try:
                    os.remove(ruta)
                    borradas += 1
                except OSError as exc:
                    log.warning("no se pudo borrar %s: %s", ruta, exc)
        return borradas

    def _borrar_credenciales(self, confirmacion: str) -> tuple[bool, str]:
        """BORRAR_CREDENCIALES SI: vacia el registro y borra las imagenes.

        Exige la palabra SI como argumento: un comando que deja sin acceso
        por QR a todo el personal no puede ejecutarse por un error de tipeo.
        El cliente de vigilancia la pide al usuario antes de enviarlo.
        """
        if confirmacion.strip() != "SI":
            return False, ("comando destructivo: enviar 'BORRAR_CREDENCIALES SI' "
                           "para confirmar")
        with self._lock_imagenes:
            n = self._registro.vaciar()
            borradas = self._borrar_imagenes()
        self._difundir(f"CREDENCIALES-BORRADAS {n}")
        return True, (f"{n} credenciales eliminadas (activas y revocadas), "
                      f"{borradas} imagenes borradas")

    def _regenerar_qr(self) -> tuple[bool, str]:
        """REGENERAR_QR: rehace las imagenes de las credenciales activas.

        Borra TODAS las imagenes de la carpeta (incluidas las de credenciales
        revocadas, que quedaban ahi sin servir) y genera de nuevo la de cada
        credencial activa, con el MISMO identificador. El registro no cambia:
        nadie gana ni pierde acceso, y un QR impreso antes sigue valiendo.
        Para invalidar una credencial esta BAJA (+ ALTA con identificador nuevo).
        """
        activas = self._registro.activas()
        fallidas: list[str] = []

        with self._lock_imagenes:
            borradas = self._borrar_imagenes()
            for cred in activas:
                ruta = self._ruta_imagen(cred.identificador)
                try:
                    generar_credencial(ruta, cred.identificador, cred.nombre, cred.rol)
                    if not verificar(ruta, cred.identificador):
                        fallidas.append(f"{cred.identificador} (no se decodifica)")
                except Exception as exc:                  # noqa: BLE001
                    log.error("no se pudo regenerar %s: %s", cred.identificador, exc)
                    fallidas.append(f"{cred.identificador} ({exc})")

        regeneradas = len(activas) - len(fallidas)
        log.info("REGENERAR_QR: %d imagenes borradas, %d de %d credenciales "
                 "regeneradas", borradas, regeneradas, len(activas))
        self._difundir(f"QR-REGENERADOS {regeneradas}")
        mensaje = (f"{regeneradas} credenciales regeneradas, "
                   f"{borradas} imagenes viejas borradas")
        if fallidas:
            return False, mensaje + " | fallaron: " + ", ".join(fallidas)
        return True, mensaje

    # ------------------------------------------------------------------ #
    # CU-13: llega una lectura de QR
    # ------------------------------------------------------------------ #
    def _al_detectar_qr(self, identificador: str, instante: float) -> None:
        """Lo llama el hilo del lector, nunca el de GStreamer (RNF-4).

        Tres caminos:
          * credencial activa con rol de acceso automatico -> se resuelve sola
          * credencial activa de visitante                 -> escala al vigilante
          * identificador desconocido o dado de baja       -> escala al vigilante

        Los dos ultimos usan el flujo de CU-3 que ya existe: si el vigilante
        no responde dentro del plazo, vence y se deniega (CU-5).
        """
        cred = self._registro.buscar(identificador)

        if cred is None:
            log.warning("QR no registrado o revocado: %s", identificador)
            ok, _ = self._nueva_solicitud(f"QR-{identificador}")
            if ok:
                self._difundir(f"QR-DESCONOCIDO {identificador} "
                               "requiere decision del vigilante")
            return

        rol = cred.rol_enum()
        etiqueta = f"{cred.identificador}-{cred.nombre.replace(' ', '_')}"

        if rol.acceso_automatico():
            log.info("QR AUTORIZADO: %s | %s | %s",
                     cred.identificador, cred.nombre, cred.rol)
            ok, _ = self._nueva_solicitud(etiqueta)
            if ok:
                self._difundir(f"QR-AUTORIZADO {cred.identificador} "
                               f"{cred.rol} {cred.nombre}")
                # La solicitud ya esta abierta: resolverla de inmediato pasa
                # por el mismo camino que una decision del vigilante, asi el
                # clip, la bitacora y el buzzer funcionan igual.
                self._resolver(True)
            return

        log.info("QR de visitante: %s | %s (requiere confirmacion)",
                 cred.identificador, cred.nombre)
        ok, _ = self._nueva_solicitud(etiqueta)
        if ok:
            self._difundir(f"QR-VISITANTE {cred.identificador} {cred.nombre} "
                           "requiere decision del vigilante")

    # ------------------------------------------------------------------ #
    # Destino de transmision automatico
    # ------------------------------------------------------------------ #
    def _al_conectar_vigilante(self, direccion: str) -> None:
        """Lo llama red.py cuando un cliente se conecta al canal de decisiones.

        La direccion sale del socket aceptado, asi que es la real del
        vigilante sin que nadie la configure. Resuelve el caso de las IP que
        rotan por DHCP: hasta ahora `host` era fijo en acceso.conf y quedaba
        vieja en minutos, con el video dejando de llegar en silencio.
        """
        if not self._cfg.streaming.seguir_cliente:
            return
        if self._pipeline.cambiar_destino(direccion):
            self._difundir(f"STREAMING hacia {direccion}:"
                           f"{self._cfg.streaming.puerto}")
    # ------------------------------------------------------------------ #
    # E3: reconexion ante falla de la camara
    # ------------------------------------------------------------------ #
    def _al_fallar_pipeline(self, mensaje: str) -> None:
        if self._reconectando.is_set() or self._parar.is_set():
            return
        self._reconectando.set()
        log.error("ALERTA: fallo de la fuente de video -> %s", mensaje)
        threading.Thread(target=self._reconectar, daemon=True).start()

    def _reconectar(self) -> None:
        cfg = self._cfg.camara
        intento = 0
        while not self._parar.is_set():
            intento += 1
            if cfg.reintentos_max and intento > cfg.reintentos_max:
                log.error("agotados %d reintentos; se detiene el servicio",
                          cfg.reintentos_max)
                self._bucle.quit()
                return

            log.warning("ALERTA: camara no disponible. Reintento %d en %.0f s",
                        intento, cfg.reintento_s)
            time.sleep(cfg.reintento_s)

            try:
                self._pipeline.liberar()
                self._pipeline.construir()
                self._pipeline.iniciar()
                log.info("camara reconectada tras %d intentos", intento)
                self._reconectando.clear()
                return
            except Exception as exc:                  # noqa: BLE001
                log.error("reintento %d fallido: %s", intento, exc)

    # ------------------------------------------------------------------ #
    def _al_senal(self) -> bool:
        log.info("senal de terminacion recibida")
        self._bucle.quit()
        return GLib.SOURCE_REMOVE

    def _volcar_dot(self, directorio: str) -> bool:
        self._pipeline.exportar_dot(directorio)
        return False

    def _apagar(self) -> None:
        log.info("apagando el servicio")
        self._parar.set()
        if self._lector is not None:
            self._lector.detener()
        if self._red is not None:
            self._red.detener()
        self._pipeline.detener()          # E4: EOS antes de NULL
        self._retencion.detener()
        self._indicadores.cerrar()
        log.info("buffer circular al cierre: %s", self._buffer.estado())
