#!/usr/bin/env python3
"""Destino de transmision automatico: la Pi transmite hacia quien se conecta.

El problema
-----------
`[streaming] host` es una IP fija en acceso.conf. En una red con DHCP de
arriendo corto esa direccion queda vieja en minutos, y el video deja de
llegar sin que nada falle: udpsink sigue enviando a una direccion que ya
no es de nadie. Es silencioso y costo varias sesiones de diagnostico.

La solucion
-----------
Cuando el vigilante se conecta al canal TCP (puerto 5001), el servidor ya
conoce su direccion: viene en el socket aceptado. Se reconfigura el udpsink
para transmitir hacia ahi.

Asi el vigilante no configura nada: se conecta y el video empieza a llegar a
su maquina, sea cual sea su IP. Si cambia de red, se reconecta y se reajusta
solo.

El `host` de la configuracion pasa a ser el valor inicial, usado hasta que
alguien se conecte. Con `host = auto` no se transmite a nadie hasta la
primera conexion, que es lo razonable para un sistema desatendido.

Aplicar desde la raiz del repositorio:
    python3 scripts/aplicar-destino-automatico.py
    python3 scripts/aplicar-destino-automatico.py --revertir
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app"


# --------------------------------------------------------------------------
# pipeline.py: metodo para cambiar el destino en caliente
# --------------------------------------------------------------------------
PIPELINE_METODO = '''
    def cambiar_destino(self, host: str, puerto: int | None = None) -> bool:
        """Redirige la transmision a otra direccion SIN reconstruir la tuberia.

        udpsink acepta cambios de `host` en caliente, en estado PLAYING. No
        hace falta parar nada: la grabacion, el buffer circular y el lector de
        QR siguen sin enterarse. Reconstruir la tuberia para esto cortaria el
        video varios segundos y perderia el contenido del buffer.

        Devuelve False si no hay rama de streaming o si el destino no cambio.
        """
        if self._udpsink is None:
            return False

        actual = self._udpsink.get_property("host")
        if actual == host and (puerto is None or
                               self._udpsink.get_property("port") == puerto):
            return False

        self._udpsink.set_property("host", host)
        if puerto is not None:
            self._udpsink.set_property("port", puerto)

        log.info("destino de transmision: %s -> %s:%d", actual, host,
                 self._udpsink.get_property("port"))
        return True

    def destino_actual(self) -> str | None:
        if self._udpsink is None:
            return None
        return (f"{self._udpsink.get_property('host')}:"
                f"{self._udpsink.get_property('port')}")
'''


# --------------------------------------------------------------------------
# servicio.py: reaccionar a la conexion del vigilante
# --------------------------------------------------------------------------
SERVICIO_METODO = '''
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
'''


def _leer(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _respaldo(p: Path) -> None:
    bak = p.with_suffix(p.suffix + ".autoip.bak")
    if not bak.exists():
        shutil.copy2(p, bak)


def _insertar(t: str, ancla: str, nuevo: str, antes: bool = False) -> str:
    i = t.index(ancla)
    if antes:
        return t[:i] + nuevo + t[i:]
    j = i + len(ancla)
    return t[:j] + nuevo + t[j:]


def aplicar() -> int:
    cambios = 0

    # ---------------- config.py ----------------
    p = APP / "acceso" / "config.py"
    t = _leer(p)
    if "seguir_cliente" in t:
        print("  config.py ya tiene seguir_cliente, se saltea")
    else:
        _respaldo(p)
        # El campo se agrega al dataclass de streaming, sea cual sea su nombre
        import re
        m = re.search(r"class StreamingCfg:\n(.*?)\n\n", t, re.S)
        if m is None:
            print("  ERROR: no encuentro StreamingCfg en config.py")
            return cambios
        bloque = m.group(0)
        nuevo = bloque.rstrip("\n") + (
            "\n    # Si es True, el destino cambia al conectarse un vigilante\n"
            "    # por TCP: su direccion sale del socket y no hace falta\n"
            "    # configurarla. Resuelve las IP que rotan por DHCP.\n"
            "    seguir_cliente: bool = True\n\n"
        )
        t = t.replace(bloque, nuevo)
        p.write_text(t, encoding="utf-8")
        print("  config.py: StreamingCfg.seguir_cliente")
        cambios += 1

    # ---------------- pipeline.py ----------------
    p = APP / "acceso" / "pipeline.py"
    t = _leer(p)
    if "cambiar_destino" in t:
        print("  pipeline.py ya tiene cambiar_destino, se saltea")
    else:
        _respaldo(p)
        # atributo
        t = _insertar(t, "        self._appsink_qr: Gst.Element | None = None",
                      "\n        self._udpsink: Gst.Element | None = None")
        # capturar el elemento al construir
        ancla = '        self._appsink_qr = self._pipeline.get_by_name("qr")'
        t = _insertar(t, ancla,
                      "", antes=True)   # no-op, el ancla se mantiene
        t = t.replace(ancla,
                      '        self._udpsink = self._pipeline.get_by_name("tx")\n'
                      + ancla)
        # metodos
        t = _insertar(t,
                      "    # ------------------------------------------------------------------ #\n"
                      "    # Ciclo de vida", PIPELINE_METODO, antes=True)
        p.write_text(t, encoding="utf-8")
        print("  pipeline.py: cambiar_destino() y destino_actual()")
        cambios += 1

    # ---------------- servicio.py ----------------
    p = APP / "acceso" / "servicio.py"
    t = _leer(p)
    if "_al_conectar_vigilante" in t:
        print("  servicio.py ya tiene _al_conectar_vigilante, se saltea")
    else:
        _respaldo(p)
        t = _insertar(t,
                      "    # ------------------------------------------------------------------ #\n"
                      "    # E3: reconexion ante falla de la camara",
                      SERVICIO_METODO, antes=True)
        p.write_text(t, encoding="utf-8")
        print("  servicio.py: _al_conectar_vigilante()")
        cambios += 1

    return cambios


def revertir() -> int:
    n = 0
    for nombre in ("config.py", "pipeline.py", "servicio.py"):
        p = APP / "acceso" / nombre
        bak = p.with_suffix(p.suffix + ".autoip.bak")
        if bak.exists():
            shutil.copy2(bak, p)
            bak.unlink()
            print(f"  restaurado {nombre}")
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
        print("Aplicando destino de transmision automatico:")
        n = aplicar()
        print(f"\n{n} archivo(s) modificado(s). Copias en *.autoip.bak")
        print("\nFALTA UN PASO MANUAL en red.py — ver "
              "CAMBIO-MANUAL-EN-RED.md")
