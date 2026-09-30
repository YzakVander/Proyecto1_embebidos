#!/bin/bash
# Prueba el buzzer pasivo por PWM de hardware SIN la aplicacion.
# Si aqui no suena, el problema es de config.txt, cableado o buffer, no de Python.
#
# Requisitos en /boot/firmware/config.txt (y reiniciar la placa):
#   dtoverlay=pwm,pin=18,func=2     PWM0 en GPIO 18 (pin fisico 12)
#   dtparam=audio=off               el audio analogico usa el mismo PWM
#
# Uso: sudo ./scripts/probar-buzzer.sh [chip] [canal]      (por omision 0 0)
set -eu

CHIP="${1:-0}"
CANAL="${2:-0}"
BASE="${PWM_BASE:-/sys/class/pwm}/pwmchip$CHIP"   # PWM_BASE solo para pruebas
PWM="$BASE/pwm$CANAL"

if [ ! -d "$BASE" ]; then
  echo "No existe $BASE."
  echo "Revise config.txt y reinicie. Chips PWM disponibles:"
  ls "${PWM_BASE:-/sys/class/pwm}" 2>/dev/null || echo "  (ninguno)"
  exit 1
fi

# Exportar el canal si hace falta y esperar a que se pueda escribir en el
EXPORTADO=0
if [ ! -d "$PWM" ]; then
  echo "$CANAL" > "$BASE/export"
  EXPORTADO=1
  for _ in $(seq 1 50); do
    [ -w "$PWM/enable" ] && break
    sleep 0.02
  done
fi
if [ ! -w "$PWM/enable" ]; then
  echo "No se puede escribir en $PWM. Correr con sudo."
  exit 1
fi

# Al salir (normal, error o Ctrl+C): silencio y liberar el canal
apagar() {
  echo 0 > "$PWM/duty_cycle" 2>/dev/null || true
  echo 0 > "$PWM/enable"     2>/dev/null || true
  if [ "$EXPORTADO" = 1 ]; then
    echo "$CANAL" > "$BASE/unexport" 2>/dev/null || true
  fi
}
trap apagar EXIT

# tono <frecuencia_hz> <duracion_ms>
tono() {
  local periodo=$((1000000000 / $1))
  echo 0                 > "$PWM/duty_cycle"   # primero 0: el nuevo period puede ser menor
  echo "$periodo"        > "$PWM/period"
  echo $((periodo / 2))  > "$PWM/duty_cycle"   # 50 % = onda cuadrada
  echo 1                 > "$PWM/enable"
  sleep "$(printf '%d.%03d' $(($2 / 1000)) $(($2 % 1000)))"
  echo 0                 > "$PWM/enable"
}

pausa() { sleep "$(printf '%d.%03d' $(($1 / 1000)) $(($1 % 1000)))"; }

echo "Usando $PWM"
echo "1) PERMITIDO: tono agudo de 2500 Hz, 800 ms"
tono 2500 800
pausa 1000

echo "2) DENEGADO: 3 pitidos graves de 800 Hz"
tono 800 200; pausa 150
tono 800 200; pausa 150
tono 800 200
pausa 1000

echo "3) Barrido de 500 a 4000 Hz (para escoger las frecuencias que mejor suenan)"
for f in 500 1000 1500 2000 2500 3000 3500 4000; do
  echo "   $f Hz"
  tono "$f" 300
  pausa 200
done

echo "Listo."
