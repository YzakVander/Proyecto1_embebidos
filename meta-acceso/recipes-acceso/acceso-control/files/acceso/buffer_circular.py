"""Buffer circular de pre-evento sobre cuadros H.264 ya comprimidos.

Por que comprimidos y no crudos
-------------------------------
A 1280x720 I420 cada cuadro crudo ocupa 1.38 MB. Guardar 5 s a 30 fps serian
207 MB en RAM, y 5 s antes + 5 s despues llegarian a 415 MB. Con cuadros ya
comprimidos a 2.5 Mbit/s, 10 s ocupan ~3 MB. Es lo que hace una camara de
vigilancia real, y ademas escribir el clip se vuelve casi una copia de bytes:
no hay que recodificar nada.

El precio es que no se puede cortar en cualquier cuadro. Un clip que empieza
en un cuadro P no se decodifica: hay que retroceder hasta el cuadro clave
(IDR) anterior. Con key-int-max=30 a 30 fps hay un IDR por segundo, asi que
el retroceso anade como mucho 1 s de contexto extra, lo cual no estorba.

Escritura del clip
------------------
El clip se guarda en MP4 (escribir_clip_mp4) para que se abra en cualquier
reproductor. Un MP4 necesita la marca de tiempo de cada cuadro: por eso el
buffer guarda pts_ns junto a los bytes. Si el empaquetado falla, el servicio
guarda el flujo crudo .h264 (escribir_clip_anexo) para no perder la evidencia;
ese archivo se convierte despues con scripts/convertir-clip.sh.

Relacion con la rubrica
-----------------------
B4: el appsink declara max-buffers y drop=true; la deque tiene maxlen propio.
B5: el callback solo copia bytes y retorna. Toda la escritura ocurre en otro
    hilo, disparada por el servicio, nunca dentro del callback.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class CuadroComprimido:
    """Un cuadro H.264 con lo minimo para poder reensamblarlo despues."""
    datos: bytes
    pts_ns: int          # marca de tiempo de presentacion, nanosegundos
    es_clave: bool       # True si es IDR (punto valido de inicio de clip)
    recibido_en: float   # time.monotonic() al llegar


class BufferCircular:
    """Guarda los ultimos N segundos de cuadros comprimidos.

    Seguro para uso concurrente: el callback de GStreamer escribe desde el
    hilo de streaming y el hilo de eventos lee para armar el clip.
    """

    def __init__(self, segundos: int, fps: int, max_buffers: int) -> None:
        # Holgura del 50 % sobre lo teorico: el codificador puede entregar
        # rafagas y no conviene perder el cuadro clave por un cuadro de mas.
        capacidad = min(int(segundos * fps * 1.5), max_buffers)
        self._cola: deque[CuadroComprimido] = deque(maxlen=capacidad)
        self._lock = threading.Lock()
        self._segundos = segundos
        self._total_recibidos = 0
        self._sin_clave = 0
        log.info(
            "buffer circular: %d s a %d fps -> capacidad %d cuadros",
            segundos, fps, capacidad,
        )

    # ------------------------------------------------------------------ #
    # Escritura: se llama desde el callback del appsink (B5: debe ser rapido)
    # ------------------------------------------------------------------ #
    def agregar(self, datos: bytes, pts_ns: int, es_clave: bool) -> None:
        cuadro = CuadroComprimido(datos, pts_ns, es_clave, time.monotonic())
        with self._lock:
            self._cola.append(cuadro)
            self._total_recibidos += 1
            if es_clave:
                self._sin_clave = 0
            else:
                self._sin_clave += 1

    # ------------------------------------------------------------------ #
    # Lectura: se llama desde el hilo de eventos
    # ------------------------------------------------------------------ #
    def instantanea(self, segundos: float | None = None) -> list[CuadroComprimido]:
        """Devuelve los cuadros de los ultimos `segundos`, desde un IDR.

        Si no hay ningun cuadro clave en la ventana, se amplia hacia atras
        hasta encontrarlo. Sin IDR el clip no se puede decodificar.
        """
        ventana = segundos if segundos is not None else self._segundos
        ahora = time.monotonic()

        with self._lock:
            todos = list(self._cola)

        if not todos:
            log.warning("buffer circular vacio al pedir instantanea")
            return []

        # 1. recortar por tiempo
        recientes = [c for c in todos if ahora - c.recibido_en <= ventana]
        if not recientes:
            recientes = todos[-1:]

        # 2. retroceder hasta el cuadro clave anterior
        idx_inicio = todos.index(recientes[0])
        while idx_inicio > 0 and not todos[idx_inicio].es_clave:
            idx_inicio -= 1

        if not todos[idx_inicio].es_clave:
            log.warning(
                "no hay cuadro clave en el buffer; el clip puede no decodificarse"
            )

        seleccion = todos[idx_inicio:]
        log.info(
            "instantanea: %d cuadros (%.1f s solicitados, inicio %s)",
            len(seleccion), ventana,
            "IDR" if todos[idx_inicio].es_clave else "NO-IDR",
        )
        return seleccion

    def estado(self) -> dict:
        """Para F2/F3: vigilar que el buffer no crezca sin control."""
        with self._lock:
            return {
                "cuadros": len(self._cola),
                "capacidad": self._cola.maxlen,
                "bytes": sum(len(c.datos) for c in self._cola),
                "total_recibidos": self._total_recibidos,
                "cuadros_desde_idr": self._sin_clave,
            }


def escribir_clip_anexo(ruta: str, cuadros: list[CuadroComprimido]) -> int:
    """Escribe los cuadros como flujo H.264 crudo (Annex B).

    Es el RESPALDO de escribir_clip_mp4: un .h264 no lleva marcas de tiempo
    ni contenedor, y muchos reproductores no lo abren. Se convierte a MP4 con
    scripts/convertir-clip.sh.
    """
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    escritos = 0
    with open(ruta, "wb") as f:
        for c in cuadros:
            f.write(c.datos)
            escritos += len(c.datos)
    log.info("clip escrito: %s (%d cuadros, %d KiB)",
             ruta, len(cuadros), escritos // 1024)
    return escritos


def escribir_clip_mp4(ruta: str, cuadros: list[CuadroComprimido], fps: int,
                      tiempo_max_s: float = 10.0) -> int:
    """Empaqueta los cuadros en un MP4 con GStreamer, sin recodificar.

        appsrc ! h264parse ! mp4mux ! filesink

    Los cuadros ya vienen comprimidos: solo se les pone la "caja" MP4. Cada
    uno lleva su marca de tiempo relativa al primero, asi el clip empieza en
    0 y dura lo mismo que el tiempo real que abarca.

    DTS = PTS porque el codificador no usa cuadros B (perfil Baseline en el
    v4l2h264enc de la RPi, tune=zerolatency en x264enc): cada cuadro se
    decodifica en el mismo orden en que se muestra.

    Corre en el hilo del clip, nunca en el de GStreamer (B5). Lanza una
    excepcion si algo falla; el servicio decide el respaldo.
    """
    # Import local: el modulo del buffer no necesita GStreamer para nada mas
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst

    Gst.init(None)
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)

    caps = ("video/x-h264,stream-format=byte-stream,alignment=au,"
            f"framerate={fps}/1")
    tuberia = Gst.parse_launch(
        f"appsrc name=fuente format=time max-bytes=0 caps={caps} "
        "! h264parse ! mp4mux ! filesink name=destino"
    )
    tuberia.get_by_name("destino").set_property("location", ruta)
    fuente = tuberia.get_by_name("fuente")
    bus = tuberia.get_bus()

    try:
        if tuberia.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("la tuberia del clip no pudo pasar a PLAYING")

        duracion_cuadro = Gst.SECOND // max(fps, 1)
        base = cuadros[0].pts_ns
        tiene_pts = all(c.pts_ns != Gst.CLOCK_TIME_NONE for c in cuadros)
        if not tiene_pts:
            log.warning("clip sin marcas de tiempo; se asumen %d fps", fps)

        # Marca de tiempo de cada cuadro, relativa al primero y nunca decreciente
        tiempos = []
        previo = 0
        for i, c in enumerate(cuadros):
            t = (c.pts_ns - base) if tiene_pts else i * duracion_cuadro
            t = max(t, previo)
            tiempos.append(t)
            previo = t

        escritos = 0
        for i, c in enumerate(cuadros):
            buf = Gst.Buffer.new_wrapped(c.datos)
            buf.pts = buf.dts = tiempos[i]
            siguiente = tiempos[i + 1] if i + 1 < len(tiempos) else tiempos[i] + duracion_cuadro
            buf.duration = max(siguiente - tiempos[i], 1)
            if not c.es_clave:
                buf.set_flags(Gst.BufferFlags.DELTA_UNIT)
            if fuente.emit("push-buffer", buf) != Gst.FlowReturn.OK:
                raise RuntimeError(f"appsrc rechazo el cuadro {i}")
            escritos += len(c.datos)

        # Fin de flujo: mp4mux escribe el indice (atomo moov) y cierra el archivo
        fuente.emit("end-of-stream")
        msg = bus.timed_pop_filtered(
            int(tiempo_max_s * Gst.SECOND),
            Gst.MessageType.EOS | Gst.MessageType.ERROR,
        )
        if msg is None:
            raise TimeoutError(f"el MP4 no se cerro en {tiempo_max_s:.0f} s")
        if msg.type == Gst.MessageType.ERROR:
            err, _debug = msg.parse_error()
            raise RuntimeError(err.message)
    finally:
        tuberia.set_state(Gst.State.NULL)

    log.info("clip escrito: %s (%d cuadros, %.1f s, %d KiB)",
             ruta, len(cuadros), (tiempos[-1] + duracion_cuadro) / Gst.SECOND,
             escritos // 1024)
    return escritos
