#!/bin/bash
# Tuberia del sistema: transmision en vivo + rama de cuadros para el lector QR.
#
# SIN videorate en la rama del QR: ese elemento, junto con su capsfilter de
# 5 fps, propaga la restriccion hacia arriba a traves del tee y choca con los
# 30 fps que necesita la rama del codificador (not-negotiated).
# La reduccion de tasa se hace en el consumidor: el lector analiza un cuadro
# cada 200 ms y descarta el resto.
set -eu
DEV="${1:-/dev/video2}"
DESTINO="${2:-127.0.0.1}"

gst-launch-1.0 -e \
  v4l2src device="$DEV" \
  ! image/jpeg,width=1280,height=720,framerate=30/1 \
  ! jpegdec \
  ! videoconvert \
  ! queue max-size-buffers=8 leaky=downstream \
  ! tee name=t_raw \
  t_raw. ! queue max-size-buffers=8 leaky=downstream \
         ! x264enc tune=zerolatency bitrate=2500 key-int-max=30 \
         ! h264parse config-interval=-1 \
         ! rtph264pay config-interval=1 pt=96 \
         ! udpsink host="$DESTINO" port=5000 sync=false \
  t_raw. ! queue max-size-buffers=1 leaky=downstream \
         ! ximagesink sync=false
