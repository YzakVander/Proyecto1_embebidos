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
from .buffer_circular import BufferCircular, escribir_clip_anexo
from .config import Config
from .decision import Bitacora, RegistroAcceso, Resultado, SolicitudAcceso, ahora_iso
from .pipeline import PipelineAcceso

log = logging.getLogger(__name__)


class ServicioAcceso:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        # El buffer debe alcanzar para la ventana COMPLETA del clip:
        # los segundos previos al evento mas los posteriores. Dimensionarlo
        # solo con segundos_antes hace que al pedir la instantanea la parte
        # mas vieja ya se haya descartado y el clip quede corto.
        self._buffer = BufferCircular(
            segundos=cfg.clips.segundos_antes + cfg.clips.segundos_despues,
            fps=cfg.codec.fps,
            max_buffers=cfg.clips.max_buffers,
        )
        self._pipeline = PipelineAcceso(cfg, self._buffer)
        self._indicadores = IndicadoresAcceso(cfg.actuador)
        self._bitacora = Bitacora(cfg.bitacora.ruta)
        self._bucle = GLib.MainLoop()

        self._pendiente: SolicitudAcceso | None = None
        self._lock_pendiente = threading.Lock()
        self._parar = threading.Event()
        self._contador = 0
        self._reconectando = threading.Event()

    # ------------------------------------------------------------------ #
    def ejecutar(self, dot_dir: str | None = None) -> int:
        self._pipeline.al_fallar(self._al_fallar_pipeline)
        self._pipeline.construir()
        self._pipeline.iniciar()

        if dot_dir:
            GLib.timeout_add_seconds(3, self._volcar_dot, dot_dir)

        threading.Thread(target=self._escuchar_eventos, daemon=True).start()

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

    def _procesar_comando(self, texto: str) -> None:
        if not texto:
            return
        partes = texto.split(maxsplit=1)
        verbo = partes[0].upper()

        if verbo == "SOLICITUD":
            ident = partes[1] if len(partes) > 1 else f"anonimo-{self._contador + 1}"
            self._nueva_solicitud(ident)
        elif verbo in ("PERMITIR", "DENEGAR"):
            self._resolver(verbo == "PERMITIR")
        elif verbo == "SALIR":
            self._bucle.quit()
        else:
            log.warning("comando no reconocido: %s", texto)

    # ------------------------------------------------------------------ #
    # CU-3: procesamiento de la solicitud
    # ------------------------------------------------------------------ #
    def _nueva_solicitud(self, identificador: str) -> None:
        with self._lock_pendiente:
            if self._pendiente is not None:
                log.warning("ya hay una solicitud en curso; se ignora '%s'",
                            identificador)
                return
            self._contador += 1
            solicitud = SolicitudAcceso(
                identificador, self._cfg.eventos.timeout_decision_s
            )
            self._pendiente = solicitud

        log.info("=== SOLICITUD #%d: %s (plazo %.0f s) ===",
                 self._contador, identificador, self._cfg.eventos.timeout_decision_s)
        threading.Thread(
            target=self._atender, args=(solicitud,), daemon=True
        ).start()

    def _resolver(self, permitido: bool) -> None:
        with self._lock_pendiente:
            solicitud = self._pendiente
        if solicitud is None:
            log.warning("no hay solicitud pendiente que resolver")
            return
        if not solicitud.resolver(permitido):
            log.warning("la solicitud ya habia vencido")

    def _atender(self, solicitud: SolicitudAcceso) -> None:
        """Hilo por solicitud: espera la decision, indica y escribe el clip."""
        inicio = time.monotonic()
        resultado = solicitud.esperar()          # H2: bloquea o vence
        latencia_ms = (time.monotonic() - inicio) * 1000.0

        permitido = resultado == Resultado.PERMITIDO
        self._indicadores.indicar(permitido)      # RF-5

        clip = None
        if self._cfg.clips.habilitados:
            clip = self._escribir_clip(solicitud.identificador)

        self._bitacora.anotar(RegistroAcceso(
            timestamp=ahora_iso(),
            identificador=solicitud.identificador,
            resultado=resultado.value,
            latencia_decision_ms=round(latencia_ms, 1),
            clip=clip,
            nota=None if resultado != Resultado.VENCIDO else
                 "denegado automaticamente por vencimiento del plazo",
        ))

        with self._lock_pendiente:
            self._pendiente = None

    def _escribir_clip(self, identificador: str) -> str | None:
        """Clip de pre-evento + post-evento desde el buffer circular."""
        cfg = self._cfg.clips
        # Esperar los segundos posteriores para que el buffer los acumule.
        time.sleep(cfg.segundos_despues)

        ventana = cfg.segundos_antes + cfg.segundos_despues
        cuadros = self._buffer.instantanea(ventana)
        if not cuadros:
            log.warning("buffer vacio; no se escribe clip")
            return None

        seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in identificador)
        nombre = f"evento_{time.strftime('%Y%m%d-%H%M%S')}_{seguro}.h264"
        ruta = os.path.join(cfg.directorio, nombre)
        escribir_clip_anexo(ruta, cuadros)
        return ruta

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
        self._pipeline.detener()          # E4: EOS antes de NULL
        self._indicadores.cerrar()
        log.info("buffer circular al cierre: %s", self._buffer.estado())
