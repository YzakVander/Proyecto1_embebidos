#!/bin/bash
# B1 - efecto de queue en las ramas de un tee.
# Se procesan N cuadros fijos y se mide el tiempo total. Sin queue, la rama
# rapida queda arrastrada por la lenta porque comparten hilo.
#
# Es un EXPERIMENTO de metodologia en la PC, no una medicion del sistema: usa
# videotestsrc y un x264enc deliberadamente lento para provocar el efecto.
# Su resultado (mediciones/B1-tee-queue.txt) justifica la regla de diseño.
# Que la tuberia real la cumple se verifica sobre su grafo: seccion B1 del
# informe de a6-grafo.sh.
set -u
MODO="${1:?uso: ./b1-tee.sh con|sin}"
if [ "$MODO" = "con" ]; then Q="queue ! "; else Q=""; fi
N=150   # 5 s de video a 30 fps

INICIO=$(date +%s.%N)
gst-launch-1.0 -q \
  videotestsrc num-buffers=$N \
  ! video/x-raw,format=I420,width=1280,height=720,framerate=30/1 \
  ! tee name=t \
  t. ! ${Q}fakesink sync=false \
  t. ! ${Q}x264enc speed-preset=veryslow ! fakesink sync=false \
  >/dev/null 2>&1
FIN=$(date +%s.%N)

echo "tee $MODO queue: $N cuadros en $(echo "$FIN - $INICIO" | bc) s"
