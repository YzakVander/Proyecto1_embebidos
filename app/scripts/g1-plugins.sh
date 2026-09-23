#!/bin/bash
# G1 - deriva qué biblioteca aporta cada elemento de la tubería.
# La lista NO se adivina: se saca de la tubería que ya funciona.
set -u
ELEMENTOS="appsink h264parse mp4mux queue rtph264pay splitmuxsink tee udpsink videotestsrc x264enc v4l2src jpegdec videoconvert capsfilter filesink"

printf '%-16s %s\n' "ELEMENTO" "BIBLIOTECA"
printf '%-16s %s\n' "--------" "----------"
for e in $ELEMENTOS; do
  lib=$(gst-inspect-1.0 "$e" 2>/dev/null | grep -m1 Filename | awk '{print $2}')
  if [ -n "$lib" ]; then
    printf '%-16s %s\n' "$e" "$(basename "$lib")"
  else
    printf '%-16s %s\n' "$e" "(no disponible en el host)"
  fi
done
