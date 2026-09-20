#!/bin/bash
# B1 - efecto de queue en las ramas de un tee.
# Se procesan N cuadros fijos y se mide el tiempo total. Sin queue, la rama
# rapida queda arrastrada por la lenta porque comparten hilo.
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
