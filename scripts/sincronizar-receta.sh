#!/bin/bash
# La receta acceso-control lleva una copia de app/ porque SRC_URI usa file://.
# Este script la mantiene al dia. EJECUTAR ANTES DE CADA bitbake.
#
# Para la entrega final esta duplicacion desaparece: SRC_URI pasa a git con
# SRCREV fijo, que es lo que exige la trazabilidad del SBOM.
set -eu
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$RAIZ/meta-acceso/recipes-acceso/acceso-control/files"

mkdir -p "$DESTINO"
rm -rf "$DESTINO/acceso"
cp -r "$RAIZ/app/acceso" "$DESTINO/acceso"
cp "$RAIZ/app/config/acceso.conf" "$DESTINO/acceso.conf"
find "$DESTINO" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "Sincronizado:"
find "$DESTINO" -type f | sed "s|$DESTINO/|  |"
