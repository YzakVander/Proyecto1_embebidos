#!/bin/bash
# CU-1 - Puesto de vigilancia: recibe y muestra el flujo RTP/H.264.
# Ejecutar en la SEGUNDA computadora (la receptora).
set -eu
PUERTO="${1:-5000}"

echo "Escuchando RTP/H.264 en UDP $PUERTO ..."
echo "Si no aparece imagen, revisar el firewall de Windows en ESTA maquina."
gst-launch-1.0 -v \
  udpsrc port="$PUERTO" \
    caps="application/x-rtp,media=(string)video,clock-rate=(int)90000,encoding-name=(string)H264,payload=(int)96" \
  ! rtpjitterbuffer latency=100 \
  ! rtph264depay ! h264parse ! avdec_h264 \
  ! videoconvert ! autovideosink sync=false
