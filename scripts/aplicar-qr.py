#!/usr/bin/env python3
"""Aplica los cambios del lector de QR sobre los modulos existentes.

Edita en el sitio: app/acceso/pipeline.py, servicio.py y config.py, y agrega
las secciones nuevas a app/config/acceso.conf.

Es idempotente: si un cambio ya esta aplicado, lo saltea. Antes de tocar
nada guarda una copia .bak de cada archivo.

Uso, desde la raiz del repositorio:
    python3 scripts/aplicar-qr.py
    python3 scripts/aplicar-qr.py --revertir     restaura los .bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app"


# ---------------------------------------------------------------------------
# Cambios: (archivo, descripcion, ancla, texto_nuevo, antes_o_despues)
# ---------------------------------------------------------------------------

CONFIG_DATACLASSES = '''
@dataclass
class QrCfg:
    """CU-13: lectura de credenciales QR con OpenCV."""
    habilitado: bool = True
    # Analisis por segundo. NO se reduce la tasa con videorate en la tuberia:
    # ese elemento propaga su capsfilter hacia arriba a traves del tee y choca
    # con los 30 fps que necesita la rama del codificador (not-negotiated,
    # verificado en pruebas). La reduccion se hace en el consumidor: el lector
    # analiza uno cada 1/analisis_por_s segundos y descarta el resto.
    analisis_por_s: float = 5.0
    # El detector trabaja sobre el cuadro reducido a este ancho. Medido:
    # 1280x720 -> 42 ms por analisis en x86 (~167 ms estimado en Cortex-A72);
    # 640 de ancho -> 15 ms (~60 ms en la Pi). La deteccion sigue funcionando
    # con la credencial ocupando el 25 % del alto del cuadro.
    ancho_analisis: int = 640
    # Se ignora el MISMO identificador durante este tiempo. Uno distinto pasa
    # de inmediato, para no bloquear a quien viene detras.
    enfriamiento_s: float = 5.0


@dataclass
class CredencialesCfg:
    """Credenciales registradas: quien tiene acceso y con que rol."""
    ruta: str = "/var/lib/acceso/credenciales.json"
    directorio: str = "/var/lib/acceso/credenciales"

'''

CONFIG_CAMPOS = """    qr: QrCfg = field(default_factory=QrCfg)
    credenciales: CredencialesCfg = field(default_factory=CredencialesCfg)
"""

CONFIG_MAPA = '        "qr": cfg.qr, "credenciales": cfg.credenciales,\n'

PIPELINE_RAMA = '''
        if c.qr.habilitado and self._lector_qr is not None:
            # Cuelga de t_raw (video SIN comprimir): OpenCV necesita imagenes,
            # no H.264. Se pide BGR, el formato nativo de OpenCV, para evitar
            # una conversion en Python por cada cuadro.
            #
            # SIN videorate y SIN ancho/alto en el capsfilter: ambos propagan
            # su restriccion hacia arriba a traves del tee y chocan con la
            # rama del codificador. El lector descarta cuadros por tiempo y
            # reduce la resolucion con cv2.resize, que es mas barato que
            # arriesgar un not-negotiated.
            #
            # leaky=downstream con un solo buffer: si el detector se atrasa,
            # interesa el presente. Un QR de hace dos segundos ya no sirve.
            partes.append(
                "t_raw. ! queue max-size-buffers=1 leaky=downstream "
                "! videoconvert ! video/x-raw,format=BGR "
                "! appsink name=qr emit-signals=true sync=false "
                "max-buffers=1 drop=true"
            )
'''

PIPELINE_CALLBACK = '''
    def _al_llegar_cuadro_qr(self, sink: Gst.Element) -> Gst.FlowReturn:
        """Entrega el cuadro al lector de QR. B5: copiar y retornar.

        La deteccion NO ocurre aqui. Este callback corre en el hilo de
        GStreamer: analizar la imagen dentro frenaria la tuberia entera,
        incluidas la transmision y la grabacion. El lector tiene su propio
        hilo y toma el ultimo cuadro cuando esta libre.
        """
        muestra = sink.emit("pull-sample")
        if muestra is None:
            return Gst.FlowReturn.OK

        buf = muestra.get_buffer()
        estructura = muestra.get_caps().get_structure(0)
        ancho = estructura.get_value("width")
        alto = estructura.get_value("height")

        ok, info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK
        try:
            # np.frombuffer NO copia: apunta a memoria de GStreamer, que se
            # libera en el unmap de abajo. El .copy() es obligatorio, no una
            # precaucion: sin el, el hilo del lector leeria memoria liberada.
            cuadro = np.frombuffer(info.data, dtype=np.uint8)
            cuadro = cuadro.reshape((alto, ancho, 3)).copy()
            self._lector_qr.entregar_cuadro(cuadro)
        except ValueError as exc:
            log.warning("cuadro QR con forma inesperada: %s", exc)
        finally:
            buf.unmap(info)

        return Gst.FlowReturn.OK
'''

SERVICIO_METODOS = '''
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
        ruta = os.path.join(self._cfg.credenciales.directorio,
                            f"{cred.identificador}.png")
        try:
            generar_credencial(ruta, cred.identificador, cred.nombre, cred.rol)
            if not verificar(ruta, cred.identificador):
                return False, (f"{cred.identificador} registrado, pero la "
                               "credencial generada no se decodifica")
        except Exception as exc:                      # noqa: BLE001
            log.error("no se pudo generar la credencial: %s", exc)
            return True, (f"{cred.identificador} registrado, pero fallo la "
                          f"generacion del PNG: {exc}")

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
'''

CONF_SECCIONES = """
[qr]
habilitado      = true
analisis_por_s  = 5.0
ancho_analisis  = 640
enfriamiento_s  = 5.0

[credenciales]
ruta      = /var/lib/acceso/credenciales.json
directorio = /var/lib/acceso/credenciales
"""


def _leer(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _escribir(p: Path, texto: str) -> None:
    p.write_text(texto, encoding="utf-8")


def _respaldo(p: Path) -> None:
    bak = p.with_suffix(p.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(p, bak)


def _insertar(texto: str, ancla: str, nuevo: str, antes: bool = False) -> str:
    i = texto.index(ancla)
    if antes:
        return texto[:i] + nuevo + texto[i:]
    j = i + len(ancla)
    return texto[:j] + nuevo + texto[j:]


def aplicar() -> int:
    cambios = 0

    # ---------------- config.py ----------------
    p = APP / "acceso" / "config.py"
    t = _leer(p)
    if "class QrCfg" in t:
        print("  config.py ya tiene QrCfg, se saltea")
    else:
        _respaldo(p)
        t = _insertar(t, "@dataclass\nclass Config:", CONFIG_DATACLASSES, antes=True)
        ancla = "    bitacora: BitacoraCfg = field(default_factory=BitacoraCfg)\n"
        t = _insertar(t, ancla, CONFIG_CAMPOS)
        ancla = '        "eventos": cfg.eventos, "bitacora": cfg.bitacora,\n'
        t = _insertar(t, ancla, CONFIG_MAPA)
        _escribir(p, t)
        print("  config.py: QrCfg, CredencialesCfg, campos y mapa")
        cambios += 1

    # ---------------- pipeline.py ----------------
    p = APP / "acceso" / "pipeline.py"
    t = _leer(p)
    if "_al_llegar_cuadro_qr" in t:
        print("  pipeline.py ya tiene la rama del QR, se saltea")
    else:
        _respaldo(p)
        if "import numpy" not in t:
            t = _insertar(t, "import gi\n", "import numpy as np\n")
        t = t.replace(
            "    def __init__(self, cfg: Config, buffer: BufferCircular) -> None:",
            "    def __init__(self, cfg: Config, buffer: BufferCircular,\n"
            "                 lector_qr=None) -> None:")
        t = _insertar(t, "        self._al_fallar = None",
                      "\n        self._lector_qr = lector_qr\n"
                      "        self._appsink_qr: Gst.Element | None = None",
                      antes=True)
        t = _insertar(t, '        return " ".join(partes)', PIPELINE_RAMA, antes=True)
        ancla = '            self._appsink.connect("new-sample", self._al_llegar_muestra)\n'
        t = _insertar(t, ancla,
                      '\n        self._appsink_qr = self._pipeline.get_by_name("qr")\n'
                      "        if self._appsink_qr is not None and self._lector_qr is not None:\n"
                      '            self._appsink_qr.connect("new-sample", self._al_llegar_cuadro_qr)\n')
        t = _insertar(t, "    # ------------------------------------------------------------------ #\n"
                         "    # Ciclo de vida", PIPELINE_CALLBACK, antes=True)
        _escribir(p, t)
        print("  pipeline.py: numpy, lector_qr, rama del appsink y callback")
        cambios += 1

    # ---------------- servicio.py ----------------
    p = APP / "acceso" / "servicio.py"
    t = _leer(p)
    if "_al_detectar_qr" in t:
        print("  servicio.py ya tiene el lector, se saltea")
    else:
        _respaldo(p)
        t = _insertar(t, "from .config import Config\n",
                      "from .credencial import generar_credencial, verificar\n"
                      "from .lector_qr import LectorQR\n"
                      "from .registro import RegistroCredenciales, Rol\n")
        ancla = "        self._bitacora = Bitacora(cfg.bitacora.ruta)\n"
        t = _insertar(t, ancla,
                      "\n        # CU-11/CU-12: credenciales registradas\n"
                      "        self._registro = RegistroCredenciales(cfg.credenciales.ruta)\n"
                      "\n        # CU-13: el lector se construye ANTES que el pipeline, que\n"
                      "        # consulta si debe agregar la rama de cuadros crudos.\n"
                      "        self._lector: LectorQR | None = None\n"
                      "        if cfg.qr.habilitado:\n"
                      "            self._lector = LectorQR(\n"
                      "                self._al_detectar_qr,\n"
                      "                enfriamiento_s=cfg.qr.enfriamiento_s,\n"
                      "                periodo_s=1.0 / max(cfg.qr.analisis_por_s, 0.1),\n"
                      "                ancho_analisis=cfg.qr.ancho_analisis,\n"
                      "            )\n")
        t = t.replace("self._pipeline = PipelineAcceso(cfg, self._buffer)",
                      "self._pipeline = PipelineAcceso(cfg, self._buffer, self._lector)")
        t = _insertar(t, "        self._pipeline.iniciar()\n",
                      "\n        if self._lector is not None:\n"
                      "            self._lector.iniciar()\n")
        t = _insertar(t, '        if verbo == "ESTADO":',
                      '        if verbo == "ALTA":\n'
                      '            return self._alta(partes[1] if len(partes) > 1 else "")\n'
                      '        if verbo == "BAJA":\n'
                      '            return self._baja(partes[1] if len(partes) > 1 else "")\n'
                      '        if verbo == "LISTAR":\n'
                      "            return True, self._registro.resumen()\n",
                      antes=True)
        t = _insertar(t, "    # ------------------------------------------------------------------ #\n"
                         "    # E3: reconexion ante falla de la camara",
                      SERVICIO_METODOS, antes=True)
        t = _insertar(t, "        self._parar.set()\n",
                      "        if self._lector is not None:\n"
                      "            self._lector.detener()\n")
        _escribir(p, t)
        print("  servicio.py: registro, lector, comandos ALTA/BAJA/LISTAR")
        cambios += 1

    # ---------------- acceso.conf ----------------
    p = APP / "config" / "acceso.conf"
    t = _leer(p)
    if "[qr]" in t:
        print("  acceso.conf ya tiene la seccion [qr], se saltea")
    else:
        _respaldo(p)
        _escribir(p, t.rstrip() + "\n" + CONF_SECCIONES)
        print("  acceso.conf: secciones [qr] y [credenciales]")
        cambios += 1

    return cambios


def revertir() -> int:
    n = 0
    for p in [APP / "acceso" / "config.py", APP / "acceso" / "pipeline.py",
              APP / "acceso" / "servicio.py", APP / "config" / "acceso.conf"]:
        bak = p.with_suffix(p.suffix + ".bak")
        if bak.exists():
            shutil.copy2(bak, p)
            bak.unlink()
            print(f"  restaurado {p.name}")
            n += 1
    return n


if __name__ == "__main__":
    if not (APP / "acceso" / "pipeline.py").exists():
        sys.exit(f"no encuentro {APP}/acceso/pipeline.py — "
                 "ejecutar desde la raiz del repositorio")

    if "--revertir" in sys.argv:
        print("Revirtiendo:")
        print(f"\n{revertir()} archivo(s) restaurado(s)")
    else:
        print("Aplicando los cambios del lector de QR:")
        n = aplicar()
        print(f"\n{n} archivo(s) modificado(s). Copias en *.bak")
        print("Verificar con:  python3 -c \"import ast,pathlib;"
              "[ast.parse(p.read_text()) for p in pathlib.Path('app/acceso').glob('*.py')];"
              "print('sintaxis OK')\"")
