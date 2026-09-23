"""Tuberia GStreamer del sistema de control de acceso.

Topologia
---------
El codificador va ANTES del tee de salida: el video se comprime una sola vez
y el flujo H.264 se reparte. Codificar dos veces desperdiciaria el
codificador por hardware del BCM2711 (el proce de la placa ), que en la practica tiene una sola
instancia util.

Notas de diseno
---------------
* El appsink cuelga del tee de H.264, no del de video crudo: asi recibe
  cuadros ya comprimidos, que es lo que el buffer circular almacena.
* Cada rama del tee lleva su propio queue. Sin el, el tee entrega los buffers
  en un solo hilo y la rama lenta bloquea a la rapida. Medido: 122 s contra
  38 s para 150 cuadros (ver mediciones/B1-tee-queue.txt).
* h264parse config-interval=-1 reinserta SPS/PPS en cada cuadro clave. Sin
  eso, un cliente que se conecta tarde nunca logra decodificar.
* El cierre se hace con EOS y espera en el bus. Matar el proceso sin EOS deja
  el MP4 sin el atomo moov y no se puede reproducir (E4).
"""

from __future__ import annotations

import logging
import os

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import GLib, Gst, GstApp  # noqa: E402,F401

from .buffer_circular import BufferCircular  # noqa: E402
from .config import Config  # noqa: E402

log = logging.getLogger(__name__)


class PipelineAcceso:
    #Constructor de la clase.
    #cfg y buffer son punteros a objetos de las clases Config y BufferCircular respectivamente
    def __init__(self, cfg: Config, buffer: BufferCircular) -> None: #Esa flecha indica lo que retorna el metodo. Este caso es equivalente void
        #Se declaran e inicializan los atributos de la clase. 
        #Se usa el guion bajo para indicar que son privados.
        self._cfg = cfg
        self._buffer = buffer
        #Punteros que tienen valor por defecto none.
        self._pipeline: Gst.Pipeline | None = None
        self._appsink: Gst.Element | None = None
        self._grabador: Gst.Element | None = None
        self._al_fallar = None          # callback que fija el servicio (E3)

    # ------------------------------------------------------------------ #
    # Construccion
    # ------------------------------------------------------------------ #
    def descripcion(self) -> str:
        c = self._cfg #Copia local del atributo _cfg
        partes = []

        conv = f"! {c.camara.convertidor} " if c.camara.convertidor else "" #Operador ternario. Asigna el nombre del convertidor si existe, 
        #sino asigna una cadena vacia.
        caps_enc = f" ! {c.codec.caps_salida}" if c.codec.caps_salida else "" #Asigna una cadena de texto con los caps de salida del codec si existen, sino asigna una cadena vacia.
        #La f es para introducir expresiones dentro del string

        partes.append(f"{c.camara.fuente} ! {c.camara.caps}") #Agrega la fuente de la camara y sus caps a la lista de partes.
        partes.append("! queue max-size-buffers=8 leaky=downstream ! tee name=t_raw") #Agrega cola de tamaño 8, su politica para overflow y genera la bifucacion.
        partes.append(
            f"t_raw. ! queue max-size-buffers=8 leaky=downstream " 
            f"{conv}! {c.codec.encoder}{caps_enc} "
            f"! h264parse config-interval=-1 ! tee name=t_h264"
        ) #Se van agregando los elementos de la rama de codificacion de video. 

        if c.grabacion.habilitada: #Si la grabacion esta habilitada en el acceso.conf...
            os.makedirs(c.grabacion.directorio, exist_ok=True)
            ruta = os.path.join(c.grabacion.directorio, c.grabacion.patron) #Junta directorio y nombre de la grabacion
            ns = int(c.grabacion.segundos_por_segmento) * 1_000_000_000 #Convierte los segundos a nanosegundos para el parametro max-size-time del splitmuxsink
            partes.append(
                f"t_h264. ! queue "
                f"! splitmuxsink name=grabador location={ruta} "
                f"max-size-time={ns} muxer-factory=mp4mux send-keyframe-requests=true"
            ) #Agrega los bloques de la rama de grabacion. Se pegan al segundo tee (tee_h264)

        if c.streaming.habilitado:
            partes.append(
                f"t_h264. ! queue max-size-buffers=8 leaky=downstream "
                f"! rtph264pay config-interval=1 pt=96 aggregate-mode=zero-latency "
                f"! udpsink name=tx host={c.streaming.host} port={c.streaming.puerto} "
                f"sync=false async=false"
            )

        if c.clips.habilitados:
            # B4: max-buffers acota la memoria y drop=true garantiza que un
            # consumidor lento jamas frene la tuberia.
            # El capsfilter byte-stream es obligatorio: sin el, h264parse
            # entrega formato 'avc' (NAL con prefijo de longitud) y el clip
            # resultante no lo puede releer ningun h264parse posterior, que
            # espera codigos de inicio 00 00 00 01. Verificado con xxd sobre
            # un clip generado sin esta linea: empezaba en 00 00 00 02.
            # alignment=au mantiene un cuadro completo por buffer.
            partes.append(
                f"t_h264. ! queue max-size-buffers=8 leaky=downstream "
                f"! h264parse ! video/x-h264,stream-format=byte-stream,alignment=au "
                f"! appsink name=captura emit-signals=true sync=false "
                f"max-buffers={c.clips.max_buffers} drop=true"
            )

        return " ".join(partes)

    def construir(self) -> None:
        Gst.init(None)
        desc = self.descripcion()
        log.info("tuberia: %s", desc)

        self._pipeline = Gst.parse_launch(desc)
        self._grabador = self._pipeline.get_by_name("grabador")
        self._appsink = self._pipeline.get_by_name("captura")

        if self._appsink is not None:
            self._appsink.connect("new-sample", self._al_llegar_muestra)

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._al_mensaje)   # E1: watch de bus

    # ------------------------------------------------------------------ #
    # B5: el callback solo copia bytes y retorna
    # ------------------------------------------------------------------ #
    def _al_llegar_muestra(self, sink: Gst.Element) -> Gst.FlowReturn:
        muestra = sink.emit("pull-sample")
        if muestra is None:
            return Gst.FlowReturn.OK

        buf = muestra.get_buffer()
        ok, info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK
        try:
            # Un cuadro clave NO lleva la bandera DELTA_UNIT.
            es_clave = not buf.has_flags(Gst.BufferFlags.DELTA_UNIT)
            self._buffer.agregar(bytes(info.data), buf.pts, es_clave)
        finally:
            buf.unmap(info)

        return Gst.FlowReturn.OK

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #
    def iniciar(self) -> None:
        assert self._pipeline is not None
        if self._pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("la tuberia no pudo pasar a PLAYING")
        log.info("tuberia en PLAYING")

    def detener(self, tiempo_eos_s: float = 10.0) -> None:
        """E4: EOS -> espera -> NULL. Sin esto el ultimo MP4 queda invalido."""
        if self._pipeline is None:
            return
        log.info("enviando EOS para cerrar los contenedores")
        self._pipeline.send_event(Gst.Event.new_eos())

        bus = self._pipeline.get_bus()
        msg = bus.timed_pop_filtered(
            int(tiempo_eos_s * Gst.SECOND),
            Gst.MessageType.EOS | Gst.MessageType.ERROR,
        )
        if msg is None:
            log.warning("no llego EOS en %.1f s; se cierra de todos modos", tiempo_eos_s)

        self._pipeline.set_state(Gst.State.NULL)
        log.info("tuberia en NULL")

    def liberar(self) -> None:
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None

    # ------------------------------------------------------------------ #
    def exportar_dot(self, directorio: str, nombre: str = "acceso") -> None:
        """A6: grafo de la tuberia real."""
        if self._pipeline is None:
            return
        os.makedirs(directorio, exist_ok=True)
        os.environ["GST_DEBUG_DUMP_DOT_DIR"] = directorio
        Gst.debug_bin_to_dot_file(self._pipeline, Gst.DebugGraphDetails.ALL, nombre)
        log.info("grafo exportado a %s/%s.dot", directorio, nombre)

    def al_fallar(self, callback) -> None:
        """E3: el servicio registra aqui su rutina de reconexion."""
        self._al_fallar = callback

    # ------------------------------------------------------------------ #
    # E1: watch de bus. Un pipeline sin esto falla en silencio.
    # ------------------------------------------------------------------ #
    def _al_mensaje(self, _bus: Gst.Bus, msg: Gst.Message) -> None:
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            log.error("GStreamer ERROR: %s | %s", err.message, debug)
            if self._al_fallar is not None:
                self._al_fallar(err.message)
        elif t == Gst.MessageType.WARNING:
            err, debug = msg.parse_warning()
            log.warning("GStreamer WARNING: %s | %s", err.message, debug)
        elif t == Gst.MessageType.EOS:
            log.info("GStreamer: fin de flujo")
        elif t == Gst.MessageType.ELEMENT:
            st = msg.get_structure()
            if st and st.get_name() == "splitmuxsink-fragment-closed":
                log.info("segmento cerrado: %s", st.get_string("location"))
