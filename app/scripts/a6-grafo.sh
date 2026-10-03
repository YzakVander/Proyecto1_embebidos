#!/bin/sh
# A1 / A2 / A5 / A6 / B1 / B3 - grafo de la tuberia REAL, generado por la
# aplicacion misma, con su configuracion real.
#
# Mejor evidencia que un gst-launch armado a mano: incluye lo que GStreamer
# inserto solo y las caps que de verdad se negociaron. Una sola corrida
# alimenta seis items del acta (ver analizar-dot.py).
#
# En la placa (como root), con este script y analizar-dot.py en la misma
# carpeta:
#     ./a6-grafo.sh
# Luego, en la PC, traer el resultado al repositorio:
#     scp root@<IP>:/tmp/grafos/acceso.dot app/grafos/
#     scp root@<IP>:/tmp/grafos/A1-A6-grafo-rpi4.txt app/mediciones/
#     dot -Tsvg -Grankdir=LR app/grafos/acceso.dot -o app/grafos/pipeline-acceso-rpi4.svg
#
# Variables (opcionales):
#     CONF  configuracion          (/etc/acceso/acceso.conf)
#     DIR   carpeta de salida      (/tmp/grafos)
#     SEG   segundos de corrida    (8; el grafo se vuelca a los 3 s)
#     APP   comando de la app      (acceso-control; en la PC: "python3 -m acceso")
#
# El bloque bcm2835-codec no admite un segundo proceso mientras el servicio
# lo usa (C1-hallazgo-contextos.txt): el script detiene el servicio, espera
# 10 s, corre la aplicacion a mano y al final lo vuelve a arrancar.
set -u
AQUI="$(cd "$(dirname "$0")" && pwd)"
CONF="${CONF:-/etc/acceso/acceso.conf}"
DIR="${DIR:-/tmp/grafos}"
SEG="${SEG:-8}"
APP="${APP:-acceso-control}"
SERVICIO=acceso-control
SALIDA="$DIR/A1-A6-grafo-rpi4.txt"

reanudar=0
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$SERVICIO" 2>/dev/null; then
    echo "deteniendo $SERVICIO (libera los contextos del bloque de hardware) ..."
    systemctl stop "$SERVICIO"
    reanudar=1
    sleep 10
fi
# Pase lo que pase, el servicio vuelve a quedar como estaba
trap '[ "$reanudar" = 1 ] && systemctl start "$SERVICIO" && echo "$SERVICIO arrancado de nuevo"' EXIT

mkdir -p "$DIR"
rm -f "$DIR"/*.dot "$DIR/app.log" "$SALIDA"     # solo lo que genera este script

# Con la correccion de exportar_dot() la variable ya no hace falta. Se
# mantiene por si la placa todavia corre una version anterior de
# pipeline.py, que solo genera el .dot si GST_DEBUG_DUMP_DOT_DIR existe
# antes de que arranque GStreamer.
echo "corriendo la aplicacion $SEG s ..."
GST_DEBUG_DUMP_DOT_DIR="$DIR" $APP -c "$CONF" --dot "$DIR" >"$DIR/app.log" 2>&1 &
PID=$!
sleep "$SEG"
kill -TERM "$PID" 2>/dev/null
wait "$PID" 2>/dev/null

if [ ! -s "$DIR/acceso.dot" ]; then
    echo "ERROR: no se genero $DIR/acceso.dot. Ultimas lineas del log:" >&2
    tail -20 "$DIR/app.log" >&2
    exit 1
fi

{
    echo "# A1/A2/A5/A6/B1/B3 - grafo de la tuberia real, volcado por la aplicacion"
    echo "# $(date -Iseconds 2>/dev/null || date) | $(uname -n) | $(uname -r)"
    echo "# $(gst-inspect-1.0 --version 2>/dev/null | sed -n 2p)"
    echo "# configuracion: $CONF"
    echo
    python3 "$AQUI/analizar-dot.py" "$DIR/acceso.dot"
} >"$SALIDA"

if command -v dot >/dev/null 2>&1; then
    dot -Tsvg -Grankdir=LR "$DIR/acceso.dot" -o "$DIR/pipeline-acceso.svg"
    echo "SVG: $DIR/pipeline-acceso.svg"
fi
echo "grafo:   $DIR/acceso.dot"
echo "informe: $SALIDA"
