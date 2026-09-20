#!/bin/bash
# D1 - latencia medida con el tracer de GStreamer
set -u
SALIDA="mediciones/D1-tracer.txt"

GST_DEBUG="GST_TRACER:7" GST_TRACERS="latency" \
timeout 20 gst-launch-1.0 -q \
  videotestsrc is-live=true \
  ! video/x-raw,format=I420,width=1280,height=720,framerate=30/1 \
  ! queue max-size-buffers=8 leaky=downstream \
  ! x264enc tune=zerolatency bitrate=2500 key-int-max=30 \
  ! h264parse config-interval=-1 \
  ! rtph264pay config-interval=1 pt=96 \
  ! udpsink host=127.0.0.1 port=5000 sync=false \
  2>&1 | grep "latency" > "$SALIDA"

echo "Muestras capturadas: $(wc -l < "$SALIDA")"
echo "--- ultimas 5 ---"
tail -5 "$SALIDA"
