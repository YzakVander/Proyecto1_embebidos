"""Verificacion de clips corruptos y politica de retencion (RF-7, CU-8).

Verificacion de corruptos (al arrancar la app)
----------------------------------------------
Un MP4 guarda su indice (caja 'moov') al CERRARSE. Si la app se detiene sin
cerrar el archivo (corte de energia, cierre forzado, falla de la camara),
el MP4 queda sin indice y ningun reproductor lo abre. verificar_corruptos()
recorre evidencia/ y eventos/ y borra esos archivos.

Para saber si un MP4 esta sano basta con leer la cabecera de 8 bytes de cada
caja de primer nivel (tamano + tipo), sin decodificar video: es Python puro,
toma milisegundos y no depende de ffprobe (funciona igual en Yocto). Sano =
las cajas suman exactamente el tamano del archivo y existe la caja 'moov'.

Se ejecuta ANTES de montar la tuberia: en ese momento no hay ningun archivo
abierto, asi que no se corre el riesgo de borrar el segmento en curso (que
legitimamente aun no tiene 'moov').

Retencion (mientras la app corre)
---------------------------------
Cada carpeta tiene su PROPIO tope en megabytes y su propia limpieza: una
nunca borra archivos de la otra.
  evidencia/  segmentos de la grabacion continua; se borran primero los de
              numero mas bajo (con la numeracion continua, los mas viejos).
  eventos/    clips de las solicitudes; se borran primero los de fecha y
              hora mas antigua segun su nombre (evento_AAAAMMDD-HHMMSS_...).
Si un archivo no tiene el nombre esperado, se ordena por su fecha de
modificacion, despues de los que si lo tienen.

Nunca se borra el segmento que se esta grabando ni un archivo modificado
hace menos de EDAD_MINIMA_S (un clip que se esta escribiendo).

La limpieza corre en su propio hilo, nunca en el de GStreamer: borrar en una
microSD puede tardar. Se dispara al arrancar, al cerrarse cada segmento,
despues de cada clip y cada INTERVALO_S como respaldo.

Por que no se usa max-files de splitmuxsink: cuenta por indice de la
ejecucion actual, no sabe nada de los clips de eventos ni de los archivos
que quedaron de ejecuciones anteriores.
"""

from __future__ import annotations

import logging
import os
import re
import struct
import threading
import time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)

MB = 1024 * 1024
EDAD_MINIMA_S = 10.0     # no se borra un archivo modificado hace menos de esto
INTERVALO_S = 60.0       # revision periodica de respaldo


# ---------------------------------------------------------------------------
# Verificacion de MP4 corruptos
# ---------------------------------------------------------------------------
def es_mp4_sano(ruta: str) -> bool:
    """True si el MP4 tiene sus cajas completas y su indice ('moov')."""
    try:
        total = os.path.getsize(ruta)
        hay_moov = False
        pos = 0
        with open(ruta, "rb") as f:
            while pos + 8 <= total:
                f.seek(pos)
                tam, tipo = struct.unpack(">I4s", f.read(8))
                if tam == 1:                        # tamano extendido de 64 bits
                    tam = struct.unpack(">Q", f.read(8))[0]
                elif tam == 0:                      # la caja llega hasta el final
                    tam = total - pos
                if tam < 8 or pos + tam > total:    # caja invalida o cortada
                    return False
                if tipo == b"moov":
                    hay_moov = True
                pos += tam
        return hay_moov and pos == total
    except OSError:
        return False


def verificar_corruptos(directorios: list[str]) -> int:
    """Borra los .mp4 corruptos de esas carpetas. Devuelve cuantos borro.

    Los .h264 (respaldo de los clips) no tienen cajas y no se revisan.
    """
    borrados = 0
    revisados = 0
    for directorio in directorios:
        try:
            entradas = list(os.scandir(directorio))
        except FileNotFoundError:
            continue
        for e in entradas:
            if not (e.is_file() and e.name.endswith(".mp4")):
                continue
            revisados += 1
            if es_mp4_sano(e.path):
                continue
            try:
                os.remove(e.path)
                borrados += 1
                log.warning("verificacion: borrado clip corrupto %s", e.path)
            except OSError as exc:
                log.error("verificacion: no se pudo borrar %s: %s", e.path, exc)
    log.info("verificacion de clips: %d revisados, %d corruptos borrados",
             revisados, borrados)
    return borrados


# ---------------------------------------------------------------------------
# Retencion
# ---------------------------------------------------------------------------
@dataclass
class Carpeta:
    """Una carpeta con su tope y su forma de ordenar por antiguedad."""
    nombre: str                              # para el log: "evidencia" o "eventos"
    directorio: str
    max_bytes: int
    clave: Callable[[str], object | None]    # nombre -> clave de orden, o None


def clave_segmento(prefijo: str) -> Callable[[str], int | None]:
    """evidencia_00042.mp4 -> 42 (el numero del segmento)."""
    patron = re.compile(re.escape(prefijo) + r"(\d+)\.mp4$")

    def clave(nombre: str) -> int | None:
        m = patron.match(nombre)
        return int(m.group(1)) if m else None
    return clave


_PATRON_EVENTO = re.compile(r"evento_(\d{8}-\d{6})_.*\.(mp4|h264)$")


def clave_evento(nombre: str) -> str | None:
    """evento_20260930-145808_S-....mp4 -> '20260930-145808' (se ordena como texto)."""
    m = _PATRON_EVENTO.match(nombre)
    return m.group(1) if m else None


class Retencion:
    def __init__(self, carpetas: list[Carpeta],
                 en_uso: Callable[[], set] = lambda: set()) -> None:
        self._carpetas = carpetas
        self._en_uso = en_uso        # rutas que no se pueden borrar (segmento abierto)
        self._despertar = threading.Event()
        self._parar = threading.Event()

    def iniciar(self) -> None:
        for c in self._carpetas:
            log.info("retencion: %s/ con tope de %d MB", c.directorio, c.max_bytes // MB)
        threading.Thread(target=self._bucle, name="retencion", daemon=True).start()
        self.solicitar()     # primera pasada: puede haber excesos de otra ejecucion

    def solicitar(self) -> None:
        """Pide una pasada de limpieza. Seguro de llamar desde cualquier hilo."""
        self._despertar.set()

    def detener(self) -> None:
        self._parar.set()
        self._despertar.set()

    def _bucle(self) -> None:
        while not self._parar.is_set():
            self._despertar.wait(INTERVALO_S)
            self._despertar.clear()
            if self._parar.is_set():
                break
            for c in self._carpetas:
                try:
                    self._aplicar(c)
                except Exception:                     # noqa: BLE001
                    log.exception("retencion: fallo inesperado en %s", c.directorio)

    def _aplicar(self, c: Carpeta) -> None:
        try:
            entradas = [e for e in os.scandir(c.directorio)
                        if e.is_file() and e.name.endswith((".mp4", ".h264"))]
        except FileNotFoundError:
            return

        archivos = []    # (con_nombre_valido, clave, ruta, tamano, mtime)
        for e in entradas:
            st = e.stat()
            k = c.clave(e.name)
            # Primero los de nombre valido (por su clave); despues el resto
            # por fecha de modificacion.
            archivos.append((k is None, k if k is not None else st.st_mtime,
                             e.path, st.st_size, st.st_mtime))

        ocupado = sum(a[3] for a in archivos)
        if ocupado <= c.max_bytes:
            return

        protegidos = {os.path.abspath(r) for r in self._en_uso() if r}
        ahora = time.time()
        candidatos = sorted(
            (a for a in archivos
             if os.path.abspath(a[2]) not in protegidos
             and ahora - a[4] >= EDAD_MINIMA_S),
            key=lambda a: (a[0], a[1]),
        )

        borrados = 0
        liberado = 0
        for _sin_nombre, _k, ruta, tamano, _m in candidatos:
            if ocupado <= c.max_bytes:
                break
            try:
                os.remove(ruta)
            except OSError as exc:
                log.warning("retencion: no se pudo borrar %s: %s", ruta, exc)
                continue
            ocupado -= tamano
            liberado += tamano
            borrados += 1
            log.info("retencion: borrado %s (%.1f MB)", os.path.basename(ruta), tamano / MB)

        if ocupado > c.max_bytes:
            log.error("retencion: %s/ sigue en %.1f MB (tope %d MB): no quedan "
                      "archivos que se puedan borrar", c.directorio,
                      ocupado / MB, c.max_bytes // MB)
        else:
            log.info("retencion: %s/ -> %d archivos borrados, %.1f MB liberados, "
                     "quedan %.1f MB", c.directorio, borrados, liberado / MB, ocupado / MB)
