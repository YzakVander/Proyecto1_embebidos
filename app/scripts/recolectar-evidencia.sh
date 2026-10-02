#!/bin/bash
# CU-2: extraccion remota de la evidencia de la Raspberry Pi 4.
#
# Se corre en la computadora de observacion. Trae por SSH la grabacion
# continua (evidencia/), los clips de las solicitudes (eventos/) y la
# bitacora (accesos.log), y fusiona los segmentos de 60 s en un unico MP4.
#
# Resultado (se limpia en cada corrida):
#   ~/recoleccion/evidencia/              segmentos originales
#   ~/recoleccion/eventos/                clips de las solicitudes
#   ~/recoleccion/accesos.log             bitacora de decisiones
#   ~/recoleccion/evidencia_continua.mp4  todos los segmentos en un archivo
#
# Requisitos en esta computadora: sshpass y ffmpeg
#   sudo apt install sshpass ffmpeg
#
# Uso: ./recolectar-evidencia.sh
#      IP=172.21.255.50 ./recolectar-evidencia.sh   (otra placa)
set -eu

# --- Configuracion -------------------------------------------------------
IP="${IP:-172.21.255.220}"
PUERTO="${PUERTO:-22}"
USUARIO="${USUARIO:-root}"
CLAVE="${CLAVE:-1234}"                  # contrasena de root en la placa
REMOTO="/var/lib/acceso"                # StateDirectory del servicio
DESTINO="${DESTINO:-$HOME/recoleccion}"
CONTINUA="evidencia_continua.mp4"

# Sin verificacion de huella: en el laboratorio la IP cambia de placa y al
# regrabar la microSD la huella cambia; con verificacion el script se
# trabaria en la pregunta yes/no o fallaria con "HOST IDENTIFICATION HAS
# CHANGED". Aceptable en una red de laboratorio, no en produccion.
SSH_OPC=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
         -o LogLevel=ERROR -o ConnectTimeout=5 -o Port="$PUERTO")

# --- Requisitos ----------------------------------------------------------
for prog in sshpass scp ffmpeg ffprobe; do
    if ! command -v "$prog" >/dev/null; then
        echo "ERROR: falta '$prog'. Instalar con: sudo apt install sshpass ffmpeg" >&2
        exit 1
    fi
done

# Copia un archivo o carpeta de la placa a DESTINO. Primero con el scp por
# defecto (SFTP en OpenSSH >= 9); si la placa no tiene servidor SFTP,
# reintenta con el protocolo scp clasico (-O), que dropbear si atiende.
copiar() {
    local origen="$1"
    sshpass -p "$CLAVE" scp -r "${SSH_OPC[@]}" \
        "$USUARIO@$IP:$origen" "$DESTINO/" 2>/dev/null && return 0
    sshpass -p "$CLAVE" scp -O -r "${SSH_OPC[@]}" \
        "$USUARIO@$IP:$origen" "$DESTINO/"
}

# --- 1. Limpieza de la recoleccion anterior ------------------------------
# Solo lo que genera este script: cualquier otro archivo en DESTINO se respeta.
mkdir -p "$DESTINO"
rm -rf "$DESTINO/evidencia" "$DESTINO/eventos" \
       "$DESTINO/accesos.log" "$DESTINO/$CONTINUA"
echo "== Recoleccion limpia en $DESTINO"

# --- 2. Transferencia ----------------------------------------------------
echo "== Conectando con $USUARIO@$IP ..."
if ! sshpass -p "$CLAVE" ssh "${SSH_OPC[@]}" "$USUARIO@$IP" true </dev/null 2>/dev/null; then
    echo "ERROR: no se pudo entrar a $USUARIO@$IP." >&2
    echo "       Revisar la IP, que la placa este encendida y la contrasena (CLAVE)." >&2
    exit 1
fi

for item in evidencia eventos accesos.log; do
    echo "   copiando $item ..."
    if ! copiar "$REMOTO/$item"; then
        echo "   AVISO: no se pudo copiar $REMOTO/$item (no existe en la placa?)" >&2
    fi
done
mkdir -p "$DESTINO/evidencia" "$DESTINO/eventos"

# --- 3. Fusion de los segmentos -------------------------------------------
# Orden por numero (sort -V: evidencia_00009 antes que evidencia_00010).
# Se descartan los que ffprobe no puede leer: el segmento que se estaba
# grabando al copiar todavia no tiene indice (moov) y no es reproducible.
echo "== Verificando segmentos ..."
LISTA="$(mktemp)"
trap 'rm -f "$LISTA"' EXIT

validos=0
descartados=()
resolucion=""
while IFS= read -r seg; do
    [ -n "$seg" ] || continue
    res="$(ffprobe -v error -select_streams v:0 \
                   -show_entries stream=width,height -of csv=p=0:s=x "$seg" </dev/null 2>/dev/null || true)"
    if [ -z "$res" ]; then
        descartados+=("$(basename "$seg")")
        continue
    fi
    # La placa graba siempre a la misma resolucion. Si un segmento difiere
    # (alguien cambio acceso.conf), unir con -c copy daria un MP4 danado:
    # mejor detenerse y avisar.
    if [ -z "$resolucion" ]; then
        resolucion="$res"
    elif [ "$res" != "$resolucion" ]; then
        echo "ERROR: $(basename "$seg") es $res y los anteriores son $resolucion." >&2
        echo "       No se pueden unir sin recodificar; los segmentos quedan en $DESTINO/evidencia/." >&2
        exit 1
    fi
    printf "file '%s'\n" "$seg" >> "$LISTA"
    validos=$((validos + 1))
done < <(ls "$DESTINO"/evidencia/evidencia_*.mp4 2>/dev/null | sort -V)

for d in "${descartados[@]+"${descartados[@]}"}"; do
    echo "   descartado (incompleto, se estaba grabando): $d"
done

if [ "$validos" -gt 0 ]; then
    echo "== Uniendo $validos segmentos ($resolucion) en $CONTINUA ..."
    # concat + -c copy: une sin recodificar, sin perder calidad y en segundos.
    # Si hubo cortes, el video pasa directo de un segmento al siguiente.
    ffmpeg -loglevel error -f concat -safe 0 -i "$LISTA" \
           -c copy -movflags +faststart "$DESTINO/$CONTINUA" </dev/null
else
    echo "   AVISO: no hay segmentos completos para unir."
fi

# --- 4. Resumen -----------------------------------------------------------
n_clips=$(ls "$DESTINO"/eventos/*.mp4 2>/dev/null | wc -l)
n_log=0
[ -f "$DESTINO/accesos.log" ] && n_log=$(wc -l < "$DESTINO/accesos.log")

echo
echo "== Resumen ($(date '+%Y-%m-%d %H:%M:%S'))"
echo "   segmentos de evidencia : $validos unidos, ${#descartados[@]} descartados"
echo "   clips de eventos       : $n_clips"
echo "   entradas en bitacora   : $n_log"
if [ -f "$DESTINO/$CONTINUA" ]; then
    dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$DESTINO/$CONTINUA" </dev/null)
    printf "   %-23s: %d min %02d s (%s)\n" "$CONTINUA" \
           "$(( ${dur%.*} / 60 ))" "$(( ${dur%.*} % 60 ))" \
           "$(du -h "$DESTINO/$CONTINUA" | cut -f1)"
fi
echo "   carpeta                : $DESTINO"
