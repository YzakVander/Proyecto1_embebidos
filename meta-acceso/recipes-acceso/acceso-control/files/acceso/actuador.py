"""Indicacion del resultado al sujeto: buzzer + mensaje en consola (RF-5, CU-4).

Al resolverse una solicitud se hacen dos cosas en el mismo instante:
  1. Suena el buzzer con un patron distinto segun el resultado.
  2. Se escribe en el log una linea destacada con el resultado, visible en la
     terminal de la placa.

Patrones (configurables en la seccion [actuador] del acceso.conf)
-----------------------------------------------------------------
  PERMITIDO  un tono agudo continuo           (2500 Hz, 800 ms)
  DENEGADO   pitidos graves cortos            (3 x 800 Hz de 200 ms, pausas de 150 ms)
  VENCIDO    igual que DENEGADO: para el sujeto es una negacion (CU-5)

Por que PWM de hardware
-----------------------
El buzzer es PASIVO: no oscila por si solo, hay que darle una onda cuadrada a
la frecuencia del tono. Conmutar un pin desde Python cada 200 us (2.5 kHz) da
un tono irregular y consume CPU que necesitan GStreamer y el codificador. El
BCM2711 tiene un generador PWM que produce la onda solo, con frecuencia exacta
y sin usar CPU. Python solo escribe la frecuencia y enciende o apaga el canal
a traves de sysfs (/sys/class/pwm), sin bibliotecas externas.

Requisitos en la placa (/boot/firmware/config.txt, luego reiniciar):
    dtoverlay=pwm,pin=18,func=2    PWM0 en GPIO 18 (pin fisico 12)
    dtparam=audio=off              el audio analogico usa el mismo PWM

Backends
--------
  pwm       sysfs; si no existe el canal, la app se detiene con error
  simulado  solo registra en el log que tono sonaria (desarrollo en la PC)
  auto      intenta pwm y, si falla, usa simulado con un aviso

Sobre H5 / RF-9: con el overlay cargado el pin arranca sin senal, asi que el
buzzer esta en silencio desde el arranque, antes de que corra este proceso.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from abc import ABC, abstractmethod

from .config import ActuadorCfg
from .decision import Resultado

log = logging.getLogger(__name__)

RUTA_PWM = "/sys/class/pwm"

# Un patron es una lista de (frecuencia_hz, duracion_ms). Frecuencia 0 = silencio.
Patron = list[tuple[int, int]]


# ---------------------------------------------------------------------------
# Salidas de tono
# ---------------------------------------------------------------------------
class SalidaTono(ABC):
    @abstractmethod
    def tono(self, frecuencia_hz: int) -> None:
        """Empieza a sonar a esa frecuencia hasta que se llame a silencio()."""

    @abstractmethod
    def silencio(self) -> None: ...

    @abstractmethod
    def cerrar(self) -> None: ...


class TonoSimulado(SalidaTono):
    def tono(self, frecuencia_hz: int) -> None:
        log.info("[SIM] buzzer %d Hz", frecuencia_hz)

    def silencio(self) -> None:
        log.debug("[SIM] buzzer en silencio")

    def cerrar(self) -> None:
        log.debug("[SIM] buzzer cerrado")


class TonoPWM(SalidaTono):
    """Canal PWM de hardware a traves de sysfs.

    Archivos del canal (todos los tiempos en nanosegundos):
      period      duracion de un ciclo completo = 1e9 / frecuencia
      duty_cycle  tiempo en alto dentro del ciclo; period/2 = onda cuadrada
      enable      1 = genera la onda, 0 = detenido
    """

    TIEMPO_EXPORT_S = 1.0   # espera maxima a que el sistema cree los archivos

    def __init__(self, chip: int, canal: int, base: str = RUTA_PWM) -> None:
        self._dir_chip = os.path.join(base, f"pwmchip{chip}")
        self._dir = os.path.join(self._dir_chip, f"pwm{canal}")
        self._canal = canal
        self._exportado_aqui = False

        if not os.path.isdir(self._dir_chip):
            raise FileNotFoundError(
                f"{self._dir_chip} no existe: falta dtoverlay=pwm,pin=18,func=2 "
                f"en /boot/firmware/config.txt o no se reinicio la placa")

        if not os.path.isdir(self._dir):
            self._escribir(os.path.join(self._dir_chip, "export"), canal)
            self._exportado_aqui = True
            # El kernel crea el directorio del canal y udev le ajusta permisos
            # unos milisegundos despues: hay que esperar a poder escribir.
            limite = time.monotonic() + self.TIEMPO_EXPORT_S
            while not os.access(os.path.join(self._dir, "enable"), os.W_OK):
                if time.monotonic() > limite:
                    raise PermissionError(
                        f"no se puede escribir en {self._dir}: correr con sudo")
                time.sleep(0.02)

        self.silencio()   # estado seguro al arrancar
        log.info("buzzer por PWM de hardware: %s", self._dir)

    def tono(self, frecuencia_hz: int) -> None:
        periodo = int(1_000_000_000 / frecuencia_hz)
        # El kernel rechaza un duty_cycle mayor que el period. Al bajar de
        # frecuencia no pasa nada, pero al SUBIR el period nuevo es menor que
        # el duty_cycle anterior: por eso primero se pone el duty_cycle en 0.
        self._escribir_attr("duty_cycle", 0)
        self._escribir_attr("period", periodo)
        self._escribir_attr("duty_cycle", periodo // 2)
        self._escribir_attr("enable", 1)

    def silencio(self) -> None:
        self._escribir_attr("duty_cycle", 0)   # salida fija en bajo
        self._escribir_attr("enable", 0)

    def cerrar(self) -> None:
        try:
            self.silencio()
        finally:
            if self._exportado_aqui:
                self._escribir(os.path.join(self._dir_chip, "unexport"), self._canal)

    def _escribir_attr(self, nombre: str, valor: int) -> None:
        self._escribir(os.path.join(self._dir, nombre), valor)

    @staticmethod
    def _escribir(ruta: str, valor: int) -> None:
        with open(ruta, "w") as f:
            f.write(str(valor))


def _construir_salida(cfg: ActuadorCfg) -> SalidaTono:
    if cfg.backend == "simulado":
        return TonoSimulado()
    try:
        return TonoPWM(cfg.pwm_chip, cfg.pwm_canal)
    except OSError as exc:
        if cfg.backend == "pwm":
            raise RuntimeError(f"no se pudo abrir el buzzer PWM -> {exc}") from exc
        log.warning("PWM no disponible (%s); se usa el buzzer simulado", exc)
        return TonoSimulado()


# ---------------------------------------------------------------------------
# Indicadores de acceso: lo que usa el servicio
# ---------------------------------------------------------------------------
class IndicadoresAcceso:
    """Buzzer + linea en consola, segun el resultado de la solicitud.

    El patron suena en su propio hilo: el servicio no espera a que termine.
    Una indicacion nueva REEMPLAZA a la que este sonando. Cada reproduccion
    lleva un numero de generacion; un hilo viejo que despierta y ve que ya no
    es el vigente se retira sin tocar el buzzer.
    """

    _VERDE = "\033[1;32m"
    _ROJO = "\033[1;31m"
    _NORMAL = "\033[0m"

    def __init__(self, cfg: ActuadorCfg) -> None:
        self._cfg = cfg
        self._salida = _construir_salida(cfg)
        self._lock = threading.Lock()   # protege la salida y _generacion
        self._generacion = 0
        # Color solo si el log va a una terminal; en archivos o en el journal
        # los codigos de escape serian basura.
        self._color = sys.stderr.isatty()

    def indicar(self, resultado: Resultado, identificador: str) -> None:
        permitido = resultado == Resultado.PERMITIDO
        self._anunciar(resultado, identificador)
        patron = self._patron_permitido() if permitido else self._patron_denegado()

        with self._lock:
            self._generacion += 1
            generacion = self._generacion
        threading.Thread(target=self._reproducir, args=(patron, generacion),
                         daemon=True).start()

    def cerrar(self) -> None:
        """Estado seguro al salir: buzzer en silencio y canal liberado."""
        with self._lock:
            self._generacion += 1   # invalida cualquier patron en curso
            try:
                self._salida.cerrar()
            except OSError as exc:
                log.warning("error al cerrar el buzzer: %s", exc)

    # ------------------------------------------------------------------ #
    def _patron_permitido(self) -> Patron:
        c = self._cfg
        return [(c.frecuencia_permitido_hz, c.duracion_permitido_ms)]

    def _patron_denegado(self) -> Patron:
        c = self._cfg
        patron: Patron = []
        for i in range(c.pitidos_denegado):
            patron.append((c.frecuencia_denegado_hz, c.duracion_pitido_ms))
            if i < c.pitidos_denegado - 1:
                patron.append((0, c.pausa_pitido_ms))
        return patron

    def _reproducir(self, patron: Patron, generacion: int) -> None:
        try:
            for frecuencia, ms in patron:
                with self._lock:
                    if generacion != self._generacion:
                        return    # otra indicacion tomo el control
                    if frecuencia > 0:
                        self._salida.tono(frecuencia)
                    else:
                        self._salida.silencio()
                time.sleep(ms / 1000.0)
            with self._lock:
                if generacion == self._generacion:
                    self._salida.silencio()
        except OSError as exc:
            log.error("error al escribir en el buzzer: %s", exc)

    def _anunciar(self, resultado: Resultado, identificador: str) -> None:
        if resultado == Resultado.PERMITIDO:
            texto, color = "ACCESO PERMITIDO", self._VERDE
        elif resultado == Resultado.VENCIDO:
            texto, color = "ACCESO DENEGADO (sin respuesta del vigilante)", self._ROJO
        else:
            texto, color = "ACCESO DENEGADO", self._ROJO

        linea = f">>>>>>>>>>  {texto}  |  {identificador}  <<<<<<<<<<"
        if self._color:
            linea = f"{color}{linea}{self._NORMAL}"
        log.info("%s", linea)
