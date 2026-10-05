#!/bin/sh
# Verificacion de salud del servicio de control de acceso.
#
#   ./verificar-pipeline.sh salud [minutos] [salida.csv]
#
# Muestrea cada 60 s y escribe un CSV con RSS, descriptores de archivo, CPU
# acumulada, temperatura y estado de throttling. Cierra F1, F2, F3 y F4 del
# acta en una sola corrida.
#
# Pensado para BusyBox: sin 'top -p', sin 'timeout', sin bash-ismos.
set -u

SUB="${1:-salud}"
MIN="${2:-240}"
CSV="${3:-/tmp/F1-salud.csv}"

[ "$SUB" = "salud" ] || { echo "uso: $0 salud [minutos] [salida.csv]"; exit 1; }

PID=$(systemctl show -p MainPID --value acceso-control 2>/dev/null)
[ -n "$PID" ] && [ "$PID" != "0" ] || { echo "acceso-control no esta corriendo"; exit 1; }

# vcgencmd no esta en todas las imagenes: se degrada sin abortar la corrida.
if command -v vcgencmd >/dev/null 2>&1; then
  TIENE_VCGENCMD=1
else
  TIENE_VCGENCMD=0
  echo "AVISO: vcgencmd no disponible; F4 (throttling) quedara sin dato."
fi

echo "ts,minuto,rss_kb,fds,ticks_cpu,temp_c,throttled,segmentos,mb_evidencia" > "$CSV"
echo "muestreando PID $PID durante $MIN minutos -> $CSV"

i=0
while [ "$i" -lt "$MIN" ]; do
  [ -d "/proc/$PID" ] || { echo "$(date '+%Y-%m-%dT%H:%M:%S%z'),$i,PROCESO_MUERTO" >> "$CSV"; break; }

  RSS=$(awk '/VmRSS/{print $2}' "/proc/$PID/status" 2>/dev/null)
  FDS=$(ls "/proc/$PID/fd" 2>/dev/null | wc -l)
  TICKS=$(awk '{print $14+$15}' "/proc/$PID/stat" 2>/dev/null)
  TEMP=$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null)

  if [ "$TIENE_VCGENCMD" = "1" ]; then
    THR=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
  else
    THR="NA"
  fi

  SEG=$(ls /var/lib/acceso/evidencia/*.mp4 2>/dev/null | wc -l)
  MB=$(du -sm /var/lib/acceso/evidencia 2>/dev/null | awk '{print $1}')

  echo "$(date '+%Y-%m-%dT%H:%M:%S%z'),$i,$RSS,$FDS,$TICKS,$TEMP,$THR,$SEG,$MB" >> "$CSV"

  i=$((i + 1))
  [ "$i" -lt "$MIN" ] && sleep 60
done

echo "--- resumen ---"
awk -F, 'NR>1 && $3 ~ /^[0-9]+$/ {
  if (n==0) {r0=$3; f0=$4}
  r1=$3; f1=$4; n++
  if ($6+0 > tmax) tmax=$6
} END {
  printf "muestras      : %d\n", n
  printf "RSS inicial   : %d kB\n", r0
  printf "RSS final     : %d kB  (delta %+d kB)\n", r1, r1-r0
  printf "fd inicial    : %d\n", f0
  printf "fd final      : %d  (delta %+d)\n", f1, f1-f0
  printf "temp maxima   : %.1f C\n", tmax
}' "$CSV"
