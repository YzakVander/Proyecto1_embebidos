#!/bin/bash
# Convierte un clip .h264 (Annex B) a MP4 reproducible.
#
# El buffer circular guarda cuadros comprimidos sin marcas de tiempo: un
# flujo elemental no las lleva. mp4mux de GStreamer las exige y falla con
# "Buffer has no PTS" -- ni h264parse ni identity las generan.
#
# ffmpeg si las deriva del framerate. El -r VA ANTES del -i: le dice que
# asuma esa tasa al LEER. Sin el, ffmpeg supone 25 fps y el clip se
# reproduce mas lento que la realidad. -c copy envuelve sin recodificar.
set -eu
IN="${1:?uso: $0 <clip.h264> [salida.mp4]}"
OUT="${2:-${IN%.h264}.mp4}"
FPS="${FPS:-30}"

ffmpeg -y -loglevel warning -r "$FPS" -i "$IN" -c copy "$OUT"

echo "-> $OUT"
ffprobe "$OUT" 2>&1 | grep -E "Duration|Stream"
