#!/usr/bin/env python3
"""Lector de QR con ventana de video: muestra lo que ve la camara y
dibuja el recuadro sobre el codigo detectado.

Separa los dos costos que la version de consola mezclaba:
  - captura y decodificacion MJPEG (lo hace OpenCV aqui; en el sistema
    real lo hace GStreamer y entrega BGR ya listo)
  - deteccion del QR (lo unico que corre en el sistema real)

Uso: ./scripts/probar-qr-visual.py [/dev/videoN]
     q o Esc para salir
"""
import sys, time
import cv2

dev = sys.argv[1] if len(sys.argv) > 1 else "/dev/video0"
idx = int(dev.replace("/dev/video", ""))

cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
if not cap.isOpened():
    sys.exit(f"no se pudo abrir {dev}")

# MJPG primero: sin esto la camara entrega YUYV y queda limitada a 320x240
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
print(f"{dev} a {int(cap.get(3))}x{int(cap.get(4))}  |  q para salir")

det = cv2.QRCodeDetector()
visto, t_visto, n, suma = None, 0.0, 0, 0.0

while True:
    ok, cuadro = cap.read()
    if not ok:
        continue

    t0 = time.monotonic()
    texto, puntos, _ = det.detectAndDecode(cuadro)
    ms = (time.monotonic() - t0) * 1000
    n += 1; suma += ms

    if texto and puntos is not None:
        p = puntos.astype(int).reshape(-1, 2)
        cv2.polylines(cuadro, [p], True, (0, 255, 0), 3)
        cv2.putText(cuadro, texto, (p[0][0], max(p[0][1] - 12, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        ahora = time.monotonic()
        if texto != visto or ahora - t_visto > 3:
            print(f"  {texto}   analisis {ms:5.1f} ms")
            visto, t_visto = texto, ahora

    cv2.putText(cuadro, f"{ms:.0f} ms  (prom {suma/n:.0f})", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.imshow("lector QR - q para salir", cuadro)
    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
        break

cap.release(); cv2.destroyAllWindows()
print(f"\n{n} cuadros, analisis promedio {suma/n:.1f} ms")
