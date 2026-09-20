"""Decision de acceso y bitacora persistente.

H1: la decision corre en su propio hilo, nunca dentro del hilo de GStreamer.
    El pipeline no puede quedar esperando a que alguien decida.

H2: hay un plazo maximo de decision. Vencido, el resultado es DENEGADO.
    El estado por omision es negar, no permitir. Esto no es una eleccion de
    estilo: un sistema de control de acceso que ante una falla abre la puerta
    es peor que uno que no abre.

H6: cada decision se anota en un archivo JSONL que sobrevive reinicios.
    Se elige archivo propio y no journald porque H6 exige verificar la
    persistencia tras un reinicio, y un archivo se inspecciona con cat.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum

log = logging.getLogger(__name__)


class Resultado(str, Enum):
    PERMITIDO = "permitido"
    DENEGADO = "denegado"
    VENCIDO = "denegado_por_vencimiento"   # H2


@dataclass
class RegistroAcceso:
    """Una linea de la bitacora. RF-4 pide ISO-8601 y el resultado."""
    timestamp: str
    identificador: str
    resultado: str
    latencia_decision_ms: float
    clip: str | None = None
    nota: str | None = None


class Bitacora:
    """H6: registro de accesos persistente, una linea JSON por evento."""

    def __init__(self, ruta: str) -> None:
        self._ruta = ruta
        self._lock = threading.Lock()
        directorio = os.path.dirname(ruta)
        if directorio:
            os.makedirs(directorio, exist_ok=True)
        log.info("bitacora de accesos: %s", ruta)

    def anotar(self, registro: RegistroAcceso) -> None:
        linea = json.dumps(asdict(registro), ensure_ascii=False)
        with self._lock:
            with open(self._ruta, "a", encoding="utf-8") as f:
                f.write(linea + "\n")
                f.flush()
                # fsync para que el registro sobreviva a un corte de energia,
                # no solo a un cierre ordenado del proceso.
                os.fsync(f.fileno())
        log.info("bitacora: %s -> %s", registro.identificador, registro.resultado)

    def leer_todo(self) -> list[dict]:
        if not os.path.exists(self._ruta):
            return []
        with open(self._ruta, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]


class SolicitudAcceso:
    """Una solicitud pendiente, con su plazo de decision.

    El vigilante responde llamando a `resolver`. Si nadie responde antes del
    plazo, `esperar` devuelve VENCIDO y el sistema deniega.
    """

    def __init__(self, identificador: str, timeout_s: float) -> None:
        self.identificador = identificador
        self._timeout_s = timeout_s
        self._evento = threading.Event()
        self._cierre = threading.Lock()
        self._resultado: Resultado | None = None

    def resolver(self, permitido: bool) -> bool:
        """Llamado por el vigilante. False si la solicitud ya esta cerrada."""
        with self._cierre:
            if self._evento.is_set():
                return False
            self._resultado = Resultado.PERMITIDO if permitido else Resultado.DENEGADO
            self._evento.set()
        return True

    def esperar(self) -> Resultado:
        """Bloquea hasta la decision o hasta que venza el plazo (H2)."""
        if self._evento.wait(self._timeout_s):
            return self._resultado or Resultado.DENEGADO

        # Al vencer hay que CERRAR la solicitud, no solo devolver VENCIDO.
        # Sin esto, un PERMITIR que llega tarde seguiria siendo aceptado y
        # abriria la puerta despues de que el sistema ya denego. La decision
        # vencida es definitiva.
        with self._cierre:
            if self._evento.is_set():
                # Carrera: alguien resolvio justo en el limite. Se respeta.
                return self._resultado or Resultado.DENEGADO
            self._resultado = Resultado.VENCIDO
            self._evento.set()

        log.warning(
            "solicitud '%s' vencida tras %.0f s: se DENIEGA por omision",
            self.identificador, self._timeout_s,
        )
        return Resultado.VENCIDO


def ahora_iso() -> str:
    """RF-4: marca de tiempo en ISO-8601 con zona horaria."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")
