#!/bin/sh
# D1 - latencia medida con el tracer de GStreamer sobre la APLICACION REAL
# (no sobre un gst-launch armado a mano), con su configuracion real.
#
# Dos mediciones en la misma corrida:
#   ruta     fuente -> cada sink (grabacion, streaming, clips, QR)
#   etapa    tiempo de cada elemento: es lo que alimenta el presupuesto de D4
# Del crudo se saca un resumen con minimo, mediana, p99 y maximo: el p99 es
# el que importa, porque lo que molesta al vigilante es el peor caso.
#
# En la placa (como root):
#     ./d1-latencia.sh
# Luego, en la PC:
#     scp root@<IP>:/tmp/d1/D1-resumen-rpi4.txt app/mediciones/
#     scp root@<IP>:/tmp/d1/D1-tracer-rpi4.txt  app/mediciones/   (crudo, opcional)
#
# Variables (opcionales):
#     CONF  configuracion          (/etc/acceso/acceso.conf)
#     DIR   carpeta de salida      (/tmp/d1)
#     SEG   segundos de medicion   (20)
#     APP   comando de la app      (acceso-control; en la PC: "python3 -m acceso")
#
# El tracer agrega algo de carga: los numeros son una cota superior. Igual
# que a6-grafo.sh, detiene el servicio para liberar el bloque de hardware y
# lo vuelve a arrancar al final.
set -u
CONF="${CONF:-/etc/acceso/acceso.conf}"
DIR="${DIR:-/tmp/d1}"
SEG="${SEG:-20}"
APP="${APP:-acceso-control}"
SERVICIO=acceso-control
CRUDO="$DIR/D1-tracer-rpi4.txt"
RESUMEN="$DIR/D1-resumen-rpi4.txt"

reanudar=0
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$SERVICIO" 2>/dev/null; then
    echo "deteniendo $SERVICIO (libera los contextos del bloque de hardware) ..."
    systemctl stop "$SERVICIO"
    reanudar=1
    sleep 10
fi
trap '[ "$reanudar" = 1 ] && systemctl start "$SERVICIO" && echo "$SERVICIO arrancado de nuevo"' EXIT

mkdir -p "$DIR"
rm -f "$CRUDO" "$RESUMEN" "$DIR/app.log"     # solo lo que genera este script

echo "midiendo $SEG s ..."
GST_TRACERS="latency(flags=pipeline+element)" GST_DEBUG="GST_TRACER:7" \
GST_DEBUG_NO_COLOR=1 $APP -c "$CONF" >"$DIR/app.log" 2>&1 &
PID=$!
sleep "$SEG"
kill -TERM "$PID" 2>/dev/null
wait "$PID" 2>/dev/null

# Solo las muestras, sin la definicion de formato que el tracer imprime al inicio
grep -E "(element-)?latency, .*time=\(guint64\)" "$DIR/app.log" >"$CRUDO"
if [ ! -s "$CRUDO" ]; then
    echo "ERROR: el tracer no produjo muestras. Ultimas lineas del log:" >&2
    tail -20 "$DIR/app.log" >&2
    exit 1
fi

{
    echo "# D1 - latencia medida con el tracer, aplicacion real durante $SEG s"
    echo "# $(date -Iseconds 2>/dev/null || date) | $(uname -n) | $(uname -r)"
    echo "# $(gst-inspect-1.0 --version 2>/dev/null | sed -n 2p)"
    echo "# configuracion: $CONF"
    echo
    python3 - "$CRUDO" <<'EOF'
import re, sys
from collections import defaultdict

rutas, etapas = defaultdict(list), defaultdict(list)
for linea in open(sys.argv[1], errors="replace"):
    t = re.search(r"time=\(guint64\)(\d+)", linea)
    if not t:
        continue
    ms = int(t.group(1)) / 1e6
    if "element-latency," in linea:
        e = re.search(r"element=\(string\)([^,]+)", linea)
        etapas[e.group(1)].append(ms)
    else:
        a = re.search(r"src-element=\(string\)([^,]+)", linea)
        b = re.search(r"sink-element=\(string\)([^,]+)", linea)
        rutas[f"{a.group(1)} -> {b.group(1)}"].append(ms)

def tabla(titulo, datos):
    print(titulo)
    print(f"  {'':<34}{'n':>6}{'min':>9}{'p50':>9}{'p99':>9}{'max':>9}   (ms)")
    for k, v in sorted(datos.items(), key=lambda x: -sorted(x[1])[len(x[1]) // 2]):
        v.sort()
        p = lambda q: v[min(len(v) - 1, int(len(v) * q))]
        print(f"  {k:<34}{len(v):>6}{v[0]:>9.2f}{p(0.5):>9.2f}{p(0.99):>9.2f}{v[-1]:>9.2f}")
    print()

tabla("== Ruta: fuente -> sink ==", rutas)
tabla("== Etapa: tiempo dentro de cada elemento (de mayor a menor mediana) ==", etapas)
EOF
    # B5: la aplicacion reporta la duracion de sus callbacks al detenerse.
    # Con el tracer activo son una cota superior.
    echo "== B5: duracion de los callbacks de los appsink (presupuesto: 33 ms por cuadro) =="
    grep -o "B5 callback.*" "$DIR/app.log" || echo "  (no aparecio el resumen de B5 en el log)"
} >"$RESUMEN"

cat "$RESUMEN"
echo "crudo:   $CRUDO ($(wc -l <"$CRUDO") muestras)"
echo "resumen: $RESUMEN"
