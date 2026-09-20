#!/bin/bash
# Guion de demostracion de los casos de uso.
# Uso: ./scripts/demo.sh   (con el servicio ya corriendo en otra terminal)
set -u
FIFO="${FIFO:-/tmp/acceso-eventos}"

paso() { echo; echo "=== $* ==="; }

paso "CU-3: solicitud PERMITIDA"
echo "SOLICITUD ID-001" > "$FIFO"; sleep 2
echo "PERMITIR"         > "$FIFO"; sleep 8

paso "CU-3: solicitud DENEGADA"
echo "SOLICITUD ID-002" > "$FIFO"; sleep 2
echo "DENEGAR"          > "$FIFO"; sleep 8

paso "CU-5 (H2): solicitud sin respuesta -> deniega por vencimiento"
echo "El plazo es de 30 s por omision. Bajarlo en acceso.conf para la demo."
echo "SOLICITUD ID-003" > "$FIFO"

echo
echo "Ver la bitacora con:  python3 -m acceso -c config/acceso.conf --ver-bitacora"
