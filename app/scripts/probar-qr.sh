#!/bin/bash
# Prueba el lector de QR SIN la aplicacion completa.
# Si aqui no detecta, el problema es de camara, enfoque o iluminacion,
# no del servicio.
#
# Uso: ./scripts/probar-qr.sh [/dev/videoN]
set -eu
DEV="${1:-/dev/video0}"

python3 - "$DEV" << 'PYEOF'
import sys, time, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
import cv2

dev = sys.argv[1]
idx = int(dev.replace("/dev/video", ""))
cap = cv2.VideoCapture(idx)
if not cap.isOpened():
    print(f"no se pudo abrir {dev}")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
det = cv2.QRCodeDetector()
print(f"Leyendo de {dev} a {int(cap.get(3))}x{int(cap.get(4))}. Ctrl+C para salir.")
print("Presente una credencial frente a la camara.\n")

visto, t_visto = None, 0.0
n = 0
try:
    while True:
        ok, cuadro = cap.read()
        if not ok:
            print("no llego cuadro"); time.sleep(0.5); continue
        n += 1
        t0 = time.monotonic()
        texto, puntos, _ = det.detectAndDecode(cuadro)
        ms = (time.monotonic() - t0) * 1000
        if texto:
            ahora = time.monotonic()
            if texto != visto or ahora - t_visto > 3:
                print(f"  QR: {texto}   (analisis {ms:.0f} ms)")
                visto, t_visto = texto, ahora
        if n % 50 == 0:
            print(f"  ... {n} cuadros, ultimo analisis {ms:.0f} ms")
        time.sleep(0.2)
except KeyboardInterrupt:
    print(f"\n{n} cuadros analizados")
finally:
    cap.release()
PYEOF
