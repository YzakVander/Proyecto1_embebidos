#!/bin/bash
# Convierte un clip .h264 (flujo elemental Annex B) a MP4 reproducible.
# El buffer circular guarda cuadros comprimidos sueltos; esto los envuelve
# en un contenedor sin recodificar.
set -eu
IN="${1:?uso: $0 <clip.h264> [salida.mp4]}"
OUT="${2:-${IN%.h264}.mp4}"

gst-launch-1.0 -e filesrc location="$IN" \
  ! h264parse ! mp4mux ! filesink location="$OUT"

echo "-> $OUT"
ffprobe "$OUT" 2>&1 | grep -E "Duration|Stream" || true
