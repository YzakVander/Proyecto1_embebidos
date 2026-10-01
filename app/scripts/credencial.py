#!/usr/bin/env python3
"""Genera una credencial desde la linea de comandos, sin el servicio.

Util para preparar credenciales en la PC antes de la demostracion.

    ./scripts/credencial.py ACC-7F3A91 "Daniel Chavarria" mantenimiento
"""
import sys, os, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.basicConfig(level=logging.INFO, format="%(message)s")

from acceso.credencial import generar_credencial, verificar

if len(sys.argv) < 4:
    print(__doc__)
    sys.exit(1)

ident, nombre, rol = sys.argv[1], sys.argv[2], sys.argv[3]
salida = sys.argv[4] if len(sys.argv) > 4 else f"{ident}.png"

generar_credencial(salida, ident, nombre, rol)
if verificar(salida, ident):
    print(f"OK  {salida}  decodifica '{ident}'")
else:
    print(f"ERROR  {salida} no se puede releer")
    sys.exit(1)
