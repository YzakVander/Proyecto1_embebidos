#!/bin/bash
# A3 / D3 - framerate CONTADO e intervalo entre cuadros clave, sobre los
# segmentos que grabo la placa (no sobre los caps, que dicen lo pedido).
#
# Se corre en la PC, despues de traer la evidencia con recolectar-evidencia.sh
# (o RECOLECTAR en vigilancia.py). Los segmentos incompletos o corruptos se
# reportan aparte: tambien son evidencia (E4).
#
# Uso: ./analizar-segmentos.sh [carpeta] [condicion]
#      ./analizar-segmentos.sh ~/recoleccion/evidencia "interior, buena luz"
#      ./analizar-segmentos.sh ~/recoleccion/evidencia "poca luz" > ../mediciones/A3-fps-poca-luz.txt
#
# Requisito: ffprobe (sudo apt install ffmpeg)
set -u
CARPETA="${1:-$HOME/recoleccion/evidencia}"
CONDICION="${2:-no registrada}"

command -v ffprobe >/dev/null || { echo "ERROR: falta ffprobe (sudo apt install ffmpeg)" >&2; exit 1; }
shopt -s nullglob
segmentos=("$CARPETA"/*.mp4)
[ ${#segmentos[@]} -gt 0 ] || { echo "ERROR: no hay .mp4 en $CARPETA" >&2; exit 1; }

echo "# A3 / D3 - analisis de segmentos grabados por la placa"
echo "# carpeta: $CARPETA"
echo "# condicion de iluminacion: $CONDICION"
echo "# $(date -Iseconds) | $(ffprobe -version | head -1 | cut -d' ' -f1-3)"
echo

sanos=()
echo "== A3: cuadros contados / duracion =="
for f in "${segmentos[@]}"; do
    n=$(basename "$f")
    datos=$(ffprobe -v error -select_streams v -count_frames \
        -show_entries stream=nb_read_frames:format=duration -of csv=p=0 "$f" 2>/dev/null | paste -sd,)
    cuadros=${datos%%,*}
    duracion=${datos##*,}
    if [ -z "$datos" ] || [ -z "$cuadros" ] || [ "$cuadros" = "N/A" ]; then
        echo "$n: ILEGIBLE ($(ffprobe -v error "$f" 2>&1 | tail -1 | sed 's/ @ 0x[0-9a-f]*//'))"
        continue
    fi
    sanos+=("$f")
    awk -v n="$n" -v c="$cuadros" -v d="$duracion" \
        'BEGIN {printf "%s: %d cuadros / %.2f s = %.2f fps\n", n, c, d, c / d}'
done
[ ${#sanos[@]} -gt 0 ] || exit 0

echo
echo "== Flujo ($(basename "${sanos[0]}")) =="
ffprobe -v error -select_streams v \
    -show_entries stream=codec_name,profile,level,width,height,avg_frame_rate \
    -of default=nw=1 "${sanos[0]}"

echo
echo "== D3: intervalo entre cuadros clave (s) y cuantas veces aparece =="
for f in "${sanos[@]}"; do
    echo "-- $(basename "$f")"
    ffprobe -v error -select_streams v -show_entries packet=pts_time,flags \
        -of csv=p=0 "$f" \
      | awk -F, '/K/ { if (p != "") printf "%.3f\n", $1 - p; p = $1 }' \
      | sort | uniq -c | sort -rn
done
