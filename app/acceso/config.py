"""Configuracion del sistema de control de acceso.

Se usa configparser (biblioteca estandar) a proposito: evita agregar
dependencias como PyYAML a la imagen de Yocto, lo que reduce el tamano del
rootfs y la superficie de CVE.

IMPORTANTE: interpolation=None es obligatorio. Los patrones de nombre de
archivo llevan '%05d' y la interpolacion por defecto de configparser los
rechaza con InterpolationSyntaxError.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field

RUTA_CONFIG_DEFECTO = "/etc/acceso/acceso.conf"

#Estos dataclass se usan para manejar la configuración de los bloques del pipeline
@dataclass #Equivalente a un struct en C. Se usa para almacenar datos sin metodos.
class CamaraCfg:
    # Fragmentos de tuberia GStreamer: se prueban tal cual con gst-launch-1.0
    # antes de ponerlos aqui.
    fuente: str = "videotestsrc is-live=true"
    caps: str = "video/x-raw,format=I420,width=1280,height=720,framerate=30/1"
    convertidor: str = ""          # vacio en desarrollo; videoconvert con camara USB
    reintento_s: float = 5.0       # E3: espera entre reintentos de reconexion
    reintentos_max: int = 0        # 0 = infinito


@dataclass
class CodecCfg:
    encoder: str = "x264enc tune=zerolatency bitrate=2500 key-int-max=30"
    caps_salida: str = ""
    fps: int = 30
    gop: int = 30                  # D3: keyframe cada 1.00 s a 30 fps


@dataclass
class GrabacionCfg:
    habilitada: bool = True
    directorio: str = "evidencia"
    patron: str = "evidencia_%05d.mp4"
    segundos_por_segmento: int = 60
    max_megabytes: int = 2048      # RF-7: politica de retencion


@dataclass
class StreamingCfg:
    habilitado: bool = True
    host: str = "127.0.0.1"
    puerto: int = 5000


@dataclass
class ClipsCfg:
    """Buffer circular de pre-evento (B4, B5)."""
    habilitados: bool = True
    directorio: str = "eventos"
    segundos_antes: int = 5
    segundos_despues: int = 5
    max_buffers: int = 600         # B4: tope duro del appsink


@dataclass
class ActuadorCfg:
    backend: str = "auto"          # auto | libgpiod | simulado
    gpio_chip: str = "/dev/gpiochip0"
    linea_permitido: int = 27
    linea_denegado: int = 22
    activo_bajo: bool = False
    pulso_ms: int = 3000


@dataclass
class EventosCfg:
    fuente: str = "fifo"           # fifo | teclado
    fifo: str = "/tmp/acceso-eventos"
    timeout_decision_s: float = 30.0   # H2: vencido -> DENIEGA
    enfriamiento_s: float = 2.0


@dataclass
class BitacoraCfg:
    """H6: registro de accesos persistente entre reinicios."""
    ruta: str = "accesos.log"

#Clase para agrupar la configuracion de los bloques del pipeline. Se usa como contenedor de los dataclass anteriores. Se usa para manejar la configuracion del pipeline de manera centralizada.
@dataclass
class Config:
    #Objetos anidados
    camara: CamaraCfg = field(default_factory=CamaraCfg) #Se utiliza field para crear instancias DIFERENTES en caso que en tiempo de corrida se
    #intente crear mas objetos de esta clase o del propio Config. De otra forma, las "instancias" compartirian el mismo puntero (solo una instancia en realidad).
    codec: CodecCfg = field(default_factory=CodecCfg)
    grabacion: GrabacionCfg = field(default_factory=GrabacionCfg)
    streaming: StreamingCfg = field(default_factory=StreamingCfg)
    clips: ClipsCfg = field(default_factory=ClipsCfg)
    actuador: ActuadorCfg = field(default_factory=ActuadorCfg)
    eventos: EventosCfg = field(default_factory=EventosCfg)
    bitacora: BitacoraCfg = field(default_factory=BitacoraCfg)
    nivel_log: str = "INFO"


def _asignar(destino, seccion) -> None: #Es parecido a un método estático: no pertenece a ninguna clase.
    """Copia las claves de una seccion del acceso.conf respetando el tipo del dataclass."""
    for clave, valor in seccion.items():
        if not hasattr(destino, clave):
            continue
        actual = getattr(destino, clave)
        if isinstance(actual, bool):
            setattr(destino, clave, valor.strip().lower() in ("1", "true", "si", "yes", "on"))
        elif isinstance(actual, int):
            setattr(destino, clave, int(valor))
        elif isinstance(actual, float):
            setattr(destino, clave, float(valor))
        else:
            setattr(destino, clave, valor.strip())


def cargar(ruta: str | None = None) -> Config: #Retorna un objeto de la clase Config. 
    #El método lee el archivo acceso.conf y lo convierte en un objeto de la clase Config. Si el archivo no existe/encuentra se usan valores predefinidos
    cfg = Config() #Genera instancia de clase Config. No se usa field porque se espera crear en tiempo de corrida solo una instancia de Config.
    ruta = ruta or os.environ.get("ACCESO_CONFIG", RUTA_CONFIG_DEFECTO) #En caso de hacer llamado sin argumento (ruta), se pone una por defecto.

    #Creador de objeto parseador
    parser = configparser.ConfigParser(
        interpolation=None, inline_comment_prefixes=(";", "#")
    )
    if not parser.read(ruta):
        return cfg

    mapa = { #Esto es un diccionario que mapea los nombres de las secciones de configuracion a los objetos de configuración correspondientes en la clase Config.
        "camara": cfg.camara, "codec": cfg.codec,
        "grabacion": cfg.grabacion, "streaming": cfg.streaming,
        "clips": cfg.clips, "actuador": cfg.actuador,
        "eventos": cfg.eventos, "bitacora": cfg.bitacora,
    }

    #Recorre cada objeto metido en el objeto de configuracion y le asigna los valores correspondientes
    for nombre, objeto in mapa.items():
        if parser.has_section(nombre):
            _asignar(objeto, parser[nombre]) 

    if parser.has_section("registro"):
        cfg.nivel_log = parser["registro"].get("nivel", cfg.nivel_log).strip().upper()

    return cfg
