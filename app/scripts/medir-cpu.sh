#!/bin/bash
# C2 - medicion de CPU del codificador. Uso: ./medir-cpu.sh <etiqueta> <encoder>
set -u
ETIQUETA="${1:?falta etiqueta}"
ENCODER="${2:-x264enc tune=zerolatency bitrate=2500}"
SALIDA="mediciones/C2-${ETIQUETA}.txt"

gst-launch-1.0 -q videotestsrc \
  ! video/x-raw,format=I420,width=1280,height=720,framerate=30/1 \
  ! $ENCODER ! fakesink sync=false >/dev/null 2>&1 &
PID=$!
sleep 5
echo "# C2 $ETIQUETA | $ENCODER | 1280x720@30 | $(date -Is)" > "$SALIDA"
top -b -n 12 -d 5 -p "$PID" | grep -E "^ *$PID" >> "$SALIDA"
kill "$PID" 2>/dev/null
wait "$PID" 2>/dev/null
echo "Listo: $SALIDA"
