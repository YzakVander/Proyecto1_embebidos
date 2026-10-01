"""Lectura de codigos QR sobre los cuadros de la camara (CU-13).

El detector corre en SU PROPIO HILO, nunca en el de GStreamer. El callback
del appsink solo deja el ultimo cuadro en una variable y retorna: si la
deteccion se hiciera dentro del callback, la tuberia entera se frenaria
cada vez que OpenCV analiza una imagen, y eso detendria tambien la
transmision y la grabacion.

Por que se descartan cuadros a proposito
----------------------------------------
Solo se guarda el ULTIMO cuadro recibido, no una cola. Si el detector se
atrasa, lo que interesa es el presente: un QR de hace dos segundos ya no
sirve para decidir. Mantener una cola solo acumularia retraso.

Enfriamiento
------------
A 5 fps, una persona que sostiene su credencial tres segundos genera quince
detecciones del mismo codigo. Sin enfriamiento serian quince solicitudes.
Se ignora el MISMO identificador durante `enfriamiento_s`; un identificador
distinto pasa de inmediato, para no bloquear a la persona que viene detras.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import cv2
import numpy as np

log = logging.getLogger(__name__)

# callback(identificador_leido, instante_monotonic_de_la_deteccion)
AlDetectar = Callable[[str, float], None]


class LectorQR:
    def __init__(self, al_detectar: AlDetectar, enfriamiento_s: float = 5.0,
                 periodo_s: float = 0.2, ancho_analisis: int = 640) -> None:
        self._al_detectar = al_detectar
        self._enfriamiento_s = enfriamiento_s
        self._periodo_s = periodo_s          # 0.2 s = 5 analisis por segundo
        # El cuadro llega a la resolucion de la camara (1280x720). Analizarlo
        # entero cuesta ~42 ms en x86 y ~167 ms estimados en el Cortex-A72.
        # Reducido a 640 de ancho baja a ~15 ms, y la deteccion sigue
        # funcionando con la credencial ocupando el 25 % del alto. El escalado
        # se hace aqui y no en la tuberia porque un videoscale con capsfilter
        # propaga su restriccion a traves del tee y rompe la negociacion de
        # la rama del codificador.
        self._ancho_analisis = ancho_analisis

        self._detector = cv2.QRCodeDetector()
        self._ultimo_cuadro: np.ndarray | None = None
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

        self._visto: dict[str, float] = {}   # identificador -> monotonic
        self._detecciones = 0
        self._descartadas = 0

    # ------------------------------------------------------------------ #
    # Entrada: la llama el callback del appsink (hilo de GStreamer)
    # ------------------------------------------------------------------ #
    def entregar_cuadro(self, cuadro: np.ndarray) -> None:
        """Deja el cuadro para el detector. Debe retornar de inmediato."""
        with self._lock:
            self._ultimo_cuadro = cuadro

    # ------------------------------------------------------------------ #
    def iniciar(self) -> None:
        self._hilo = threading.Thread(target=self._bucle, name="lector-qr",
                                      daemon=True)
        self._hilo.start()
        log.info("lector de QR activo (%.0f analisis/s, enfriamiento %.0f s)",
                 1.0 / self._periodo_s, self._enfriamiento_s)

    def detener(self) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=2.0)

    # ------------------------------------------------------------------ #
    def _bucle(self) -> None:
        while not self._parar.wait(self._periodo_s):
            with self._lock:
                cuadro = self._ultimo_cuadro
                self._ultimo_cuadro = None     # no analizar dos veces el mismo
            if cuadro is None:
                continue
            try:
                self._analizar(cuadro)
            except cv2.error as exc:
                # Pasa cuando el detector localiza algo parecido a un QR pero
                # con geometria degenerada (area cero): un reflejo, un borde en
                # movimiento. Es frecuente con la camara en mano, asi que va a
                # debug y no a warning para no inundar el log.
                log.debug("cuadro descartado por el detector: %s", exc)

    def _analizar(self, cuadro: np.ndarray) -> None:
        alto, ancho = cuadro.shape[:2]
        if self._ancho_analisis and ancho > self._ancho_analisis:
            escala = self._ancho_analisis / ancho
            cuadro = cv2.resize(cuadro, (self._ancho_analisis,
                                         int(alto * escala)),
                                interpolation=cv2.INTER_AREA)

        texto, puntos, _recta = self._detector.detectAndDecode(cuadro)
        if not texto or puntos is None:
            return

        instante = time.monotonic()
        identificador = texto.strip()

        anterior = self._visto.get(identificador)
        if anterior is not None and instante - anterior < self._enfriamiento_s:
            self._descartadas += 1
            return

        self._visto[identificador] = instante
        self._detecciones += 1
        log.info("QR detectado: %s", identificador)
        self._al_detectar(identificador, instante)

        self._limpiar_vistos(instante)

    def _limpiar_vistos(self, ahora: float) -> None:
        """Evita que el diccionario crezca sin limite en operacion continua."""
        if len(self._visto) < 64:
            return
        vencidos = [k for k, t in self._visto.items()
                    if ahora - t > self._enfriamiento_s * 4]
        for k in vencidos:
            del self._visto[k]

    # ------------------------------------------------------------------ #
    def estado(self) -> dict:
        return {
            "detecciones": self._detecciones,
            "descartadas_por_enfriamiento": self._descartadas,
            "identificadores_en_memoria": len(self._visto),
        }
