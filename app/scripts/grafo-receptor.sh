#!/bin/bash
# Grafo GStreamer del receptor del puesto de vigilancia (equivalente a A6,
# pero del lado de la computadora que recibe el video).
#
# Corre la MISMA tuberia que abre puesto-vigilancia.py, con
# GST_DEBUG_DUMP_DOT_DIR definido, durante unos segundos de video real. La
# cierra con SIGINT (no SIGTERM): solo asi gst-launch-1.0 escribe el volcado
# PLAYING_PAUSED, que es el unico con los caps ya negociados en cada enlace.
# Despues lo convierte a imagen con Graphviz.
#
# Con -i, el propio script abre el canal TCP con la placa durante la captura:
# al conectarse, la placa redirige el video a esta computadora, asi que no
# hace falta tener abierto ningun cliente.
#
# Uso:
#   ./grafo-receptor.sh -i <IP de la placa>          (lo normal)
#   ./grafo-receptor.sh                               (si un cliente ya esta conectado
#                                                      y su ventana de video cerrada)
# Opciones:
#   -i IP        IP de la placa; abre TCP 5001 para que redirija el video aqui
#   -p PUERTO    puerto UDP del video (por omision 5000)
#   -t SEGUNDOS  segundos de video antes de cerrar (por omision 10)
#   -o DIR       carpeta de salida (por omision ./grafos-receptor)
#   -f FORMATO   formato de la imagen: svg, png o pdf (por omision svg)
#   -s SINK      sink de video (por omision autovideosink; fakesink sin pantalla)
#
# Requisitos: gstreamer1.0-tools, plugins good, bad y libav, y graphviz
#   sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-good \
#        gstreamer1.0-plugins-bad gstreamer1.0-libav graphviz
set -euo pipefail

IP=""
PUERTO_TCP=5001
PUERTO=5000
SEGUNDOS=10
DIR="./grafos-receptor"
FORMATO="svg"
SINK="autovideosink"

uso() { sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit "${1:-0}"; }

while getopts "i:p:t:o:f:s:h" op; do
    case "$op" in
        i) IP="$OPTARG" ;;
        p) PUERTO="$OPTARG" ;;
        t) SEGUNDOS="$OPTARG" ;;
        o) DIR="$OPTARG" ;;
        f) FORMATO="$OPTARG" ;;
        s) SINK="$OPTARG" ;;
        h) uso 0 ;;
        *) uso 1 ;;
    esac
done

error() { echo "ERROR: $*" >&2; exit 1; }
aviso() { echo "AVISO: $*" >&2; }

# --- Requisitos ------------------------------------------------------------
command -v gst-launch-1.0 >/dev/null || error "falta gst-launch-1.0 (sudo apt install gstreamer1.0-tools)"
gst-inspect-1.0 avdec_h264 >/dev/null 2>&1 || error "falta avdec_h264 (sudo apt install gstreamer1.0-libav)"
TIENE_DOT=1
command -v dot >/dev/null || { TIENE_DOT=0; aviso "falta Graphviz (sudo apt install graphviz): solo quedara el .dot"; }
[[ "$SEGUNDOS" =~ ^[0-9]+$ && "$SEGUNDOS" -ge 2 ]] || error "-t debe ser un entero >= 2"

# Dos tuberias en el mismo puerto UDP arrancan sin error (udpsrc usa
# SO_REUSEADDR), pero solo una recibe el video. Se revisa en /proc, que existe
# en cualquier Linux aunque no este instalado ss.
PUERTO_HEX="$(printf '%04X' "$PUERTO")"
if awk -v p=":$PUERTO_HEX" 'FNR > 1 && substr($2, length($2) - 4) == p { hay = 1 } END { exit !hay }' \
        /proc/net/udp /proc/net/udp6 2>/dev/null; then
    error "el puerto UDP $PUERTO ya esta en uso (probablemente la ventana de video de un cliente). Cerrarla y repetir."
fi

# --- Preparacion -----------------------------------------------------------
mkdir -p "$DIR"
DIR="$(cd "$DIR" && pwd)"
rm -f "$DIR"/*gst-launch*.dot "$DIR/gst-launch.log"     # solo lo que genera este script

# Canal TCP: mientras este descriptor siga abierto, la placa transmite aqui.
if [ -n "$IP" ]; then
    echo "== Conectando con $IP:$PUERTO_TCP para que la placa redirija el video ..."
    { exec 3<>"/dev/tcp/$IP/$PUERTO_TCP"; } 2>/dev/null \
        || error "no se pudo conectar a $IP:$PUERTO_TCP (placa apagada, IP equivocada o servicio detenido)"
    if read -r -t 3 saludo <&3; then
        echo "   placa: $saludo"
        [[ "$saludo" == OK* ]] || error "la placa rechazo la conexion (revisar red_clientes en acceso.conf)"
    else
        aviso "la placa no respondio el saludo; se continua de todos modos"
    fi
fi

cerrar_tcp() { [ -n "$IP" ] && exec 3>&- 2>/dev/null || true; }

# --- Captura ---------------------------------------------------------------
# Misma tuberia que puesto-vigilancia.py (ReceptorVideo.abrir).
CAPS="application/x-rtp,media=(string)video,clock-rate=(int)90000,encoding-name=(string)H264,payload=(int)96"

echo "== Recibiendo video en UDP $PUERTO durante $SEGUNDOS s ..."
GST_DEBUG_DUMP_DOT_DIR="$DIR" gst-launch-1.0 \
    udpsrc port="$PUERTO" caps="$CAPS" \
    ! rtpjitterbuffer latency=100 \
    ! rtph264depay ! h264parse ! avdec_h264 \
    ! videoconvert \
    ! fpsdisplaysink video-sink="$SINK" sync=false text-overlay=false \
    >"$DIR/gst-launch.log" 2>&1 &
GST_PID=$!

# Ctrl+C sobre el script: cortar la captura antes, pero igual generar el grafo
INTERRUMPIDO=0
trap 'INTERRUMPIDO=1' INT

for ((s = 0; s < SEGUNDOS; s++)); do
    if ! kill -0 "$GST_PID" 2>/dev/null; then
        cerrar_tcp
        echo "--- gst-launch.log ---" >&2
        tail -n 15 "$DIR/gst-launch.log" >&2
        error "gst-launch-1.0 termino antes de tiempo (ver $DIR/gst-launch.log)"
    fi
    [ "$INTERRUMPIDO" = 1 ] && { echo "   captura interrumpida a los $s s"; break; }
    sleep 1
done
trap - INT

# SIGINT, no SIGTERM: es lo que hace que gst-launch pase por PLAYING -> PAUSED
# y escriba ese volcado.
kill -INT "$GST_PID" 2>/dev/null || true
for _ in $(seq 1 50); do
    kill -0 "$GST_PID" 2>/dev/null || break
    sleep 0.1
done
if kill -0 "$GST_PID" 2>/dev/null; then
    aviso "gst-launch-1.0 no cerro en 5 s; se fuerza"
    kill -KILL "$GST_PID" 2>/dev/null || true
fi
wait "$GST_PID" 2>/dev/null || true
cerrar_tcp

# --- Grafo -----------------------------------------------------------------
ORIGEN="$(ls -t "$DIR"/*PLAYING_PAUSED*.dot 2>/dev/null | head -n 1 || true)"
if [ -z "$ORIGEN" ]; then
    ORIGEN="$(ls -t "$DIR"/*.dot 2>/dev/null | head -n 1 || true)"
    [ -n "$ORIGEN" ] || error "gst-launch-1.0 no genero ningun .dot (ver $DIR/gst-launch.log)"
    aviso "no hay volcado PLAYING_PAUSED; se usa $(basename "$ORIGEN"), que puede no tener los caps negociados"
fi
cp "$ORIGEN" "$DIR/receptor.dot"

# Si no llego video, el decodificador nunca negocio: el enlace hacia
# avdec_h264 no tiene caps fijos (sin width) y el grafo sale sin ellos.
CAPS_H264="$(grep -E -- '-> avdec_h264.*video/x-h264.*width: ' "$DIR/receptor.dot" | head -n 1 || true)"
if [ -z "$CAPS_H264" ]; then
    aviso "no llego video: el grafo muestra los elementos pero no los caps negociados."
    if [ -n "$IP" ]; then
        aviso "revisar que el servicio este transmitiendo y que el firewall permita UDP $PUERTO."
    else
        aviso "usar -i <IP de la placa> para que la placa redirija el video a esta computadora."
    fi
fi

if [ "$TIENE_DOT" = 1 ]; then
    dot -T"$FORMATO" -Grankdir=LR "$DIR/receptor.dot" -o "$DIR/receptor.$FORMATO" \
        || error "Graphviz no pudo generar receptor.$FORMATO"
fi

# --- Resumen ---------------------------------------------------------------
campo() { grep -oE "$1: [^\\\\]+" <<<"$CAPS_H264" | head -n 1 | sed "s/^$1: //" || true; }

echo
echo "== Grafo del receptor"
echo "   volcado usado : $(basename "$ORIGEN")"
echo "   grafo .dot    : $DIR/receptor.dot"
[ "$TIENE_DOT" = 1 ] && echo "   imagen        : $DIR/receptor.$FORMATO"
if [ -n "$CAPS_H264" ]; then
    echo "   H.264 recibido: $(campo width)x$(campo height) a $(campo framerate) fps," \
         "perfil $(campo profile), nivel $(campo level)"
fi
echo "   log           : $DIR/gst-launch.log"
