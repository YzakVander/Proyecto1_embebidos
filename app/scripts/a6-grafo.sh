#!/bin/bash
# A6 - genera el grafo .dot del pipeline completo y lo convierte a PNG
set -u
mkdir -p grafos
export GST_DEBUG_DUMP_DOT_DIR=grafos
rm -f grafos/*.dot

gst-launch-1.0 -q -e videotestsrc num-buffers=90 is-live=true \
  ! video/x-raw,format=I420,width=1280,height=720,framerate=30/1 \
  ! queue max-size-buffers=8 leaky=downstream ! tee name=t_raw \
  t_raw. ! queue max-size-buffers=8 leaky=downstream \
    ! x264enc tune=zerolatency bitrate=2500 key-int-max=30 \
    ! h264parse config-interval=-1 ! tee name=t_h264 \
  t_h264. ! queue \
    ! splitmuxsink location=evidencia/evidencia_%05d.mp4 \
      max-size-time=30000000000 muxer-factory=mp4mux \
  t_h264. ! queue max-size-buffers=8 leaky=downstream \
    ! rtph264pay config-interval=1 pt=96 \
    ! udpsink host=127.0.0.1 port=5000 sync=false \
  t_raw. ! queue max-size-buffers=1 leaky=downstream \
    ! valve name=valvula_foto drop=false \
    ! jpegenc quality=85 \
    ! multifilesink location=evidencia/evento_%05d.jpg

echo "--- .dot generados ---"
ls grafos/*.dot
DOT=$(ls grafos/*PLAYING*.dot 2>/dev/null | tail -1)
if [ -n "${DOT:-}" ]; then
  dot -Tpng "$DOT" -o grafos/pipeline-acceso.png
  echo "PNG: grafos/pipeline-acceso.png"
fi
