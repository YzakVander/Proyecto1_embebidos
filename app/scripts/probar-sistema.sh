#!/bin/bash
# Topologia real: jpegdec -> tee, y cada rama con su propio convertidor.
# El videoconvert NO puede ir antes del tee: el tee impone las mismas caps a
# todas sus ramas, y aqui una quiere I420 (codificador) y otra BGR (OpenCV).
set -eu
DEV="${1:-/dev/video2}"
DESTINO="${2:-127.0.0.1}"
SINK="${SINK:-autovideosink}"

gst-launch-1.0 -e \
  v4l2src device="$DEV" ! image/jpeg,width=1280,height=720,framerate=30/1 \
  ! jpegdec ! queue max-size-buffers=8 leaky=downstream ! tee name=t_raw \
  t_raw. ! queue max-size-buffers=8 leaky=downstream \
    ! videoconvert ! video/x-raw,format=I420 \
    ! x264enc tune=zerolatency bitrate=2500 key-int-max=30 \
    ! h264parse config-interval=-1 \
    ! rtph264pay config-interval=1 pt=96 \
    ! udpsink host="$DESTINO" port=5000 sync=false \
  t_raw. ! queue max-size-buffers=1 leaky=downstream \
    ! videorate ! video/x-raw,framerate=5/1 \
    ! videoscale ! videoconvert ! video/x-raw,format=BGR,width=640,height=480 \
    ! "$SINK" sync=false
