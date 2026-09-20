"""Conmutacion de los LED de estado (RF-5, CU-4).

Dos lineas GPIO: una indica acceso permitido y otra acceso denegado. La
activacion es por PULSO, no por nivel: la linea vuelve sola a reposo tras el
intervalo configurado. Si el proceso muere con una linea activa, el indicador
quedaria mintiendo.

Tres backends con seleccion automatica:
  1. libgpiod v2  - API moderna (gpiod.request_lines), kernels 5.10+
  2. libgpiod v1  - API previa (gpiod.Chip / get_line)
  3. simulado     - solo registra en bitacora; permite desarrollar sin GPIO

Sobre H5: el estado de las lineas durante el arranque, antes de que corra
este proceso, NO se controla desde aqui. Se fija en config.txt de la
Raspberry Pi con `gpio=<n>=op,dl`. Es responsabilidad del rol de plataforma.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod

from .config import ActuadorCfg

log = logging.getLogger(__name__)


class BackendSalida(ABC):
    @abstractmethod
    def escribir(self, linea: int, activo: bool) -> None: ...

    @abstractmethod
    def cerrar(self) -> None: ...


class BackendSimulado(BackendSalida):
    def escribir(self, linea: int, activo: bool) -> None:
        log.info("[SIM] GPIO %d -> %s", linea, "ACTIVO" if activo else "reposo")

    def cerrar(self) -> None:
        log.debug("[SIM] backend cerrado")


class BackendLibgpiodV2(BackendSalida):
    def __init__(self, cfg: ActuadorCfg, lineas: list[int]) -> None:
        import gpiod
        from gpiod.line import Direction, Value

        self._Value = Value
        self._activo_bajo = cfg.activo_bajo
        inicial = Value.ACTIVE if cfg.activo_bajo else Value.INACTIVE
        config = {
            ln: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=inicial)
            for ln in lineas
        }
        self._req = gpiod.request_lines(
            cfg.gpio_chip, consumer="acceso-control", config=config
        )
        log.info("libgpiod v2: lineas %s de %s reservadas", lineas, cfg.gpio_chip)

    def escribir(self, linea: int, activo: bool) -> None:
        alto = activo != self._activo_bajo
        self._req.set_value(
            linea, self._Value.ACTIVE if alto else self._Value.INACTIVE
        )

    def cerrar(self) -> None:
        self._req.release()


class BackendLibgpiodV1(BackendSalida):
    def __init__(self, cfg: ActuadorCfg, lineas: list[int]) -> None:
        import gpiod

        self._activo_bajo = cfg.activo_bajo
        self._chip = gpiod.Chip(cfg.gpio_chip)
        self._lineas = {}
        for ln in lineas:
            l = self._chip.get_line(ln)
            l.request(
                consumer="acceso-control",
                type=gpiod.LINE_REQ_DIR_OUT,
                default_vals=[1 if cfg.activo_bajo else 0],
            )
            self._lineas[ln] = l
        log.info("libgpiod v1: lineas %s reservadas", lineas)

    def escribir(self, linea: int, activo: bool) -> None:
        alto = activo != self._activo_bajo
        self._lineas[linea].set_value(1 if alto else 0)

    def cerrar(self) -> None:
        for l in self._lineas.values():
            l.release()
        self._chip.close()


def _construir_backend(cfg: ActuadorCfg, lineas: list[int]) -> BackendSalida:
    if cfg.backend == "simulado":
        return BackendSimulado()

    fallos = []
    for nombre, clase in (("v2", BackendLibgpiodV2), ("v1", BackendLibgpiodV1)):
        try:
            return clase(cfg, lineas)
        except Exception as exc:                      # noqa: BLE001
            fallos.append(f"{nombre}: {exc}")

    if cfg.backend == "libgpiod":
        raise RuntimeError("no se pudo abrir libgpiod -> " + " | ".join(fallos))

    log.warning("libgpiod no disponible (%s); se usa backend simulado",
                " | ".join(fallos))
    return BackendSimulado()


class IndicadoresAcceso:
    """Conmuta los LED segun el resultado, con pulso temporizado."""

    def __init__(self, cfg: ActuadorCfg) -> None:
        self._cfg = cfg
        self._lineas = [cfg.linea_permitido, cfg.linea_denegado]
        self._backend = _construir_backend(cfg, self._lineas)
        self._lock = threading.Lock()
        self._ocupado = False

    def indicar(self, permitido: bool, duracion_ms: int | None = None) -> bool:
        """Enciende el LED correspondiente. False si ya hay un pulso en curso."""
        with self._lock:
            if self._ocupado:
                log.warning("indicacion ignorada: pulso en curso")
                return False
            self._ocupado = True

        linea = self._cfg.linea_permitido if permitido else self._cfg.linea_denegado
        ms = duracion_ms if duracion_ms is not None else self._cfg.pulso_ms
        threading.Thread(target=self._pulso, args=(linea, ms), daemon=True).start()
        return True

    def _pulso(self, linea: int, ms: int) -> None:
        try:
            log.info("LED GPIO %d encendido por %d ms", linea, ms)
            self._backend.escribir(linea, True)
            time.sleep(ms / 1000.0)
        finally:
            self._backend.escribir(linea, False)
            log.info("LED GPIO %d apagado", linea)
            with self._lock:
                self._ocupado = False

    def cerrar(self) -> None:
        """Estado seguro al salir: ambas lineas en reposo."""
        for ln in self._lineas:
            try:
                self._backend.escribir(ln, False)
            except Exception:                          # noqa: BLE001
                pass
        self._backend.cerrar()
