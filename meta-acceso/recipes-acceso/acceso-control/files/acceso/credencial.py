"""Generacion de la credencial: imagen BMP con el QR, el nombre y el rol.

Formato BMP: OpenCV lo escribe y lo lee con su codec interno, sin depender
de libpng. Asi la credencial funciona igual en la PC y en la imagen de
Yocto, sin importar con que codecs se haya compilado OpenCV. El archivo
pesa mas (~1.2 MB, medido), pero es irrelevante para unas pocas credenciales.

Se usa cv2.QRCodeEncoder, que ya viene en la imagen de Yocto (modulo
objdetect de OpenCV 4.13). No hace falta la biblioteca `qrcode` de Python ni
ninguna dependencia nueva: se genera y se lee con la misma biblioteca.

Que lleva cada parte
--------------------
  DENTRO del QR    solo el identificador opaco (ACC-7F3A91)
  FUERA, impreso   nombre y rol, como texto legible

Asi la credencial funciona como identificacion visual -alguien la mira y sabe
de quien es- pero una foto del QR no revela datos personales, y la baja la
invalida aunque la imagen siga circulando.

La imagen se guarda en la placa y se entrega a la persona por el medio que
sea (mensajeria, impresion). Un QR en la pantalla de un celular se lee bien
con el brillo alto.
"""

from __future__ import annotations

import logging
import os

import cv2
import numpy as np

log = logging.getLogger(__name__)

# Colores BGR (OpenCV no usa RGB)
_NEGRO = (0, 0, 0)
_BLANCO = (255, 255, 255)
_GRIS = (120, 120, 120)

_FUENTE = cv2.FONT_HERSHEY_SIMPLEX


def generar_qr(texto: str, lado_px: int = 480) -> np.ndarray:
    """Imagen BGR del QR, cuadrada, con el texto codificado."""
    encoder = cv2.QRCodeEncoder.create()
    qr = encoder.encode(texto)          # imagen binaria pequena (modulos)

    # INTER_NEAREST es obligatorio: cualquier interpolacion suave difumina los
    # bordes de los modulos y el detector deja de reconocerlos de forma fiable.
    qr = cv2.resize(qr, (lado_px, lado_px), interpolation=cv2.INTER_NEAREST)

    if len(qr.shape) == 2:
        qr = cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)
    return qr


def generar_credencial(ruta: str, identificador: str, nombre: str, rol: str,
                       titulo: str = "CONTROL DE ACCESO",
                       lado_qr: int = 480) -> str:
    """Escribe la imagen de la credencial y devuelve su ruta.

    El formato lo decide la extension de la ruta (cv2.imwrite); el servicio
    usa .bmp.

    Diseno: titulo arriba, QR centrado, nombre y rol debajo, identificador
    al pie en gris. El margen blanco alrededor del QR no es decorativo: el
    detector necesita esa "zona tranquila" para localizar el codigo.
    """
    margen = 60
    alto_cabecera = 70
    alto_pie = 150

    ancho = lado_qr + margen * 2
    alto = alto_cabecera + lado_qr + alto_pie
    lienzo = np.full((alto, ancho, 3), 255, dtype=np.uint8)

    # --- titulo ---
    _texto_centrado(lienzo, titulo, y=42, ancho=ancho,
                    escala=0.62, grosor=2, color=_NEGRO)
    cv2.line(lienzo, (margen, 54), (ancho - margen, 54), _GRIS, 1)

    # --- QR ---
    qr = generar_qr(identificador, lado_qr)
    y0 = alto_cabecera
    lienzo[y0:y0 + lado_qr, margen:margen + lado_qr] = qr

    # --- nombre y rol ---
    y = y0 + lado_qr + 46
    _texto_centrado(lienzo, nombre.upper(), y=y, ancho=ancho,
                    escala=0.80, grosor=2, color=_NEGRO)
    _texto_centrado(lienzo, rol.capitalize(), y=y + 38, ancho=ancho,
                    escala=0.62, grosor=1, color=_NEGRO)
    _texto_centrado(lienzo, identificador, y=y + 74, ancho=ancho,
                    escala=0.48, grosor=1, color=_GRIS)

    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    if not cv2.imwrite(ruta, lienzo):
        raise OSError(f"no se pudo escribir la credencial en {ruta}")

    log.info("credencial generada: %s (%s, %s)", ruta, nombre, rol)
    return ruta


def _texto_centrado(img: np.ndarray, texto: str, y: int, ancho: int,
                    escala: float, grosor: int, color: tuple) -> None:
    (w, _), _ = cv2.getTextSize(texto, _FUENTE, escala, grosor)
    x = max((ancho - w) // 2, 4)
    cv2.putText(img, texto, (x, y), _FUENTE, escala, color, grosor, cv2.LINE_AA)


def verificar(ruta: str, esperado: str) -> bool:
    """Relee la credencial recien generada y comprueba que el QR se decodifica.

    Vale la pena: una credencial que no se puede leer es peor que no tenerla,
    porque el fallo aparece recien cuando la persona esta en la puerta.
    """
    img = cv2.imread(ruta)
    if img is None:
        log.error("no se pudo releer la credencial %s", ruta)
        return False
    detector = cv2.QRCodeDetector()
    leido, _puntos, _recta = detector.detectAndDecode(img)
    if leido != esperado:
        log.error("la credencial %s decodifica '%s' y no '%s'",
                  ruta, leido, esperado)
        return False
    return True
