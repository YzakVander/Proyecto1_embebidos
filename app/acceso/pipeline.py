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
import re
import time

import gi
import numpy as np

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import GLib, Gst, GstApp  # noqa: E402,F401

from .buffer_circular import BufferCircular  # noqa: E402
from .config import Config  # noqa: E402

log = logging.getLogger(__name__)


class PipelineAcceso:
    #Constructor de la clase.
    #cfg y buffer son punteros a objetos de las clases Config y BufferCircular respectivamente
    def __init__(self, cfg: Config, buffer: BufferCircular,
                 lector_qr=None) -> None: #Esa flecha indica lo que retorna el metodo. Este caso es equivalente void
        #Se declaran e inicializan los atributos de la clase. 
        #Se usa el guion bajo para indicar que son privados.
        self._cfg = cfg
        self._buffer = buffer
        #Punteros que tienen valor por defecto none.
        self._pipeline: Gst.Pipeline | None = None
        self._appsink: Gst.Element | None = None
        self._grabador: Gst.Element | None = None

        self._lector_qr = lector_qr
        self._appsink_qr: Gst.Element | None = None
        self._udpsink: Gst.Element | None = None
        self._al_fallar = None          # callback que fija el servicio (E3)
        self._al_cerrar_segmento = None # callback que fija el servicio (RF-7: retencion)
        # Segmento MP4 que se esta grabando: la retencion no lo puede borrar
        self.segmento_actual: str | None = None

    #Funcin que va leyendo el objeto de configuracion y va armando la tuberia en forma de cadena de texto
    def descripcion(self) -> str: #Devuelve la cadena que describe el pipeline
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
            # B3: profundidad declarada, no heredada. Son los mismos valores
            # que el queue por omision aplica en la practica (a 30 fps el
            # tope de 1 s llega antes que el de 200 buffers o 10 MB), pero
            # escritos: 1 s absorbe el jitter de escritura a la microSD y
            # esta rama no es la de baja latencia. Sin leaky: la evidencia
            # no se descarta (B2). El nombre lo usa detener() (E4).
            partes.append(
                f"t_h264. ! queue name=queue_grabacion "
                f"max-size-buffers=0 max-size-bytes=0 "
                f"max-size-time=1000000000 "
                f"! splitmuxsink name=grabador location={ruta} "
                f"max-size-time={ns} muxer-factory=mp4mux send-keyframe-requests=true"
            ) #Agrega los bloques de la rama de grabacion. Se pegan al segundo tee (tee_h264)

        if c.streaming.habilitado: #Si la rama de streaming esta habilitada en el acceso.conf...
            partes.append(
                f"t_h264. ! queue max-size-buffers=8 leaky=downstream "
                f"! rtph264pay config-interval=1 pt=96 aggregate-mode=zero-latency "
                f"! udpsink name=tx host={c.streaming.host} port={c.streaming.puerto} "
                f"sync=false async=false"
            ) #Se agregan los bloques de la rama de streaming. Se pegan al segundo tee (tee_h264)

        if c.clips.habilitados: #Revisar esto...
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


        if c.qr.habilitado and self._lector_qr is not None:
            # Cuelga de t_raw, que reparte lo que entrega la camara: con una
            # webcam UVC eso es MJPEG, no video crudo. Por eso la rama lleva
            # el mismo convertidor que la de codificacion. OpenCV necesita
            # imagenes,
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
                f"t_raw. ! queue max-size-buffers=1 leaky=downstream "
                f"! {c.camara.convertidor} ! video/x-raw,format=BGR "
                "! appsink name=qr emit-signals=true sync=false "
                "max-buffers=1 drop=true"
            )
        return " ".join(partes) #Une todos los elementos de la lista partes en un solo string. Entre cada elemento coloca un espacio vacio. Este es el comando a ejecutar por GStreamer para crear la tuberia.

    def construir(self) -> None:
        Gst.init(None) #Inicializa GStreamer
        desc = self.descripcion() #Se extrae la cadena de texto que describe el pipeline
        log.info("tuberia: %s", desc) #Se guarda en el log la descripcion del pipeline

        #Se generan el pipeline con ayuda de la libreria GStreamer. Se extraen elementos particulares
        self._pipeline = Gst.parse_launch(desc)
        self._grabador = self._pipeline.get_by_name("grabador") #Puntero del sink de grabacion.
        self._appsink = self._pipeline.get_by_name("captura") #Investigar...

        # Numeracion continua: el primer segmento de esta tuberia sigue al de
        # numero mas alto que ya exista, asi un reinicio de la app (o una
        # reconexion E3, que reconstruye la tuberia) nunca sobrescribe nada.
        if self._grabador is not None:
            indice = self._siguiente_indice()
            self._grabador.set_property("start-index", indice)
            log.info("grabacion continua: primer segmento con numero %d", indice)

        if self._appsink is not None:
            self._appsink.connect("new-sample", self._al_llegar_muestra)

        self._udpsink = self._pipeline.get_by_name("tx")
        self._appsink_qr = self._pipeline.get_by_name("qr")
        if self._appsink_qr is not None and self._lector_qr is not None:
            self._appsink_qr.connect("new-sample", self._al_llegar_cuadro_qr)

        bus = self._pipeline.get_bus() #Se obtiene puntero al bus de comunicacion entre el pipeline y python
        bus.add_signal_watch() #Convierte los mensajes del bus en señales de Python.
        bus.connect("message", self._al_mensaje)   # Pega los mensajes del bus a la funcion que maneja los mensajes del bus

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
    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #
    def iniciar(self) -> None:
        assert self._pipeline is not None
        if self._pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("la tuberia no pudo pasar a PLAYING")
        log.info("tuberia en PLAYING")

    def detener(self, tiempo_cierre_s: float = 5.0) -> None:
        """E4 / B6: cierre ordenado. El ultimo MP4 tiene que quedar reproducible.

        Coordinacion del EOS entre los sinks (B6)
        -----------------------------------------
        Solo splitmuxsink escribe un archivo que se corrompe si no recibe EOS
        (sin la caja moov no se puede reproducir). udpsink y los dos appsink
        no tienen nada que cerrar. Por eso la grabacion recibe su PROPIO EOS,
        inyectado directamente en su queue, y se espera a que splitmuxsink
        confirme el cierre del segmento.

        Por que no basta con el EOS a la fuente: para llegar a splitmuxsink
        tiene que atravesar v4l2jpegdec, v4l2convert y v4l2h264enc, que al
        recibirlo vacian el bloque bcm2835-codec. En la RPi 4 ese vaciado no
        termina nunca: el EOS no llegaba en 10 s y el segmento quedaba con
        mdat=0 y sin moov (mediciones/E4-cierre-limpio.txt y
        E4-eos-no-llega.txt). El EOS a la fuente se sigue enviando para que
        las demas ramas cierren si pueden, pero ya no se espera.

        tiempo_cierre_s debe caber holgado en TimeoutStopSec=20 de la unidad.
        """
        if self._pipeline is None:
            return
        log.info("enviando EOS para cerrar los contenedores")
        self._pipeline.send_event(Gst.Event.new_eos())

        bus = self._pipeline.get_bus()
        cola = self._pipeline.get_by_name("queue_grabacion")
        if cola is None:
            # Sin rama de grabacion no hay archivo que cerrar: se espera el
            # EOS general como antes, solo para cerrar ordenadamente.
            msg = bus.timed_pop_filtered(
                int(tiempo_cierre_s * Gst.SECOND),
                Gst.MessageType.EOS | Gst.MessageType.ERROR,
            )
            if msg is None:
                log.warning("no llego EOS en %.1f s; se cierra de todos modos",
                            tiempo_cierre_s)
        else:
            cola.get_static_pad("sink").send_event(Gst.Event.new_eos())
            self._esperar_cierre_segmento(bus, tiempo_cierre_s)

        self._pipeline.set_state(Gst.State.NULL)
        log.info("tuberia en NULL")

    def _esperar_cierre_segmento(self, bus: Gst.Bus, tiempo_s: float) -> bool:
        """Espera el mensaje splitmuxsink-fragment-closed del ultimo segmento.

        El bucle de GLib ya termino, asi que el watch del bus (_al_mensaje) no
        consume los mensajes: se leen aqui directamente.
        """
        limite = time.monotonic() + tiempo_s
        while True:
            restante = limite - time.monotonic()
            if restante <= 0:
                log.error("el segmento %s no se cerro en %.1f s: puede quedar "
                          "irreproducible", self.segmento_actual, tiempo_s)
                return False
            msg = bus.timed_pop_filtered(
                int(restante * Gst.SECOND),
                Gst.MessageType.ELEMENT | Gst.MessageType.ERROR,
            )
            if msg is None:
                continue
            if msg.type == Gst.MessageType.ERROR:
                err, _debug = msg.parse_error()
                log.error("error al cerrar la grabacion: %s", err.message)
                return False
            st = msg.get_structure()
            if st and st.get_name() == "splitmuxsink-fragment-closed":
                log.info("segmento cerrado al detener: %s", st.get_string("location"))
                return True

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

    def al_cerrar_segmento(self, callback) -> None:
        """RF-7: el servicio registra aqui la solicitud de limpieza."""
        self._al_cerrar_segmento = callback

    def _siguiente_indice(self) -> int:
        """Numero mas alto de los segmentos existentes + 1 (0 si no hay ninguno).

        Se deduce del patron del acceso.conf (p. ej. evidencia_%05d.mp4): lo
        que va antes y despues del %...d.
        """
        g = self._cfg.grabacion
        m = re.match(r"(.*)%0?\d*d(.*)$", g.patron)
        if m is None:
            return 0
        patron = re.compile(re.escape(m.group(1)) + r"(\d+)" + re.escape(m.group(2)) + "$")
        try:
            nombres = os.listdir(g.directorio)
        except FileNotFoundError:
            return 0
        numeros = [int(x.group(1)) for x in map(patron.match, nombres) if x]
        return max(numeros) + 1 if numeros else 0

    def al_fallar(self, callback) -> None:
        """E3: el servicio registra aqui su rutina de reconexion."""
        self._al_fallar = callback

    #Funcion que maneja los mensajes generados por el pipelne. Sin esto, el pipeline podria fallar sin dar aviso
    #Revisar bien la implementación de esta funcion. Tengo mis dudas sobre cómo funciona.
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
            if st and st.get_name() == "splitmuxsink-fragment-opened":
                self.segmento_actual = st.get_string("location")
            if st and st.get_name() == "splitmuxsink-fragment-closed":
                log.info("segmento cerrado: %s", st.get_string("location"))
                if self._al_cerrar_segmento is not None:
                    self._al_cerrar_segmento()
