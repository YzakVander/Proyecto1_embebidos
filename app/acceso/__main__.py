"""Punto de entrada: python3 -m acceso"""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__
from .config import RUTA_CONFIG_DEFECTO, cargar


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="acceso-control",
        description="Sistema de control de acceso con GStreamer (TEC)",
    )
    ap.add_argument("-c", "--config", default=None,
                    help=f"archivo de configuracion (por defecto {RUTA_CONFIG_DEFECTO})")
    ap.add_argument("--nivel", default=None, help="DEBUG | INFO | WARNING | ERROR")
    ap.add_argument("--dot", metavar="DIR", help="exporta el grafo A6 al directorio")
    ap.add_argument("--mostrar-tuberia", action="store_true",
                    help="imprime la tuberia equivalente de gst-launch-1.0 y termina")
    ap.add_argument("--ver-bitacora", action="store_true",
                    help="muestra la bitacora de accesos y termina (H6)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)

    cfg = cargar(args.config)
    logging.basicConfig(
        level=getattr(logging, (args.nivel or cfg.nivel_log).upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)-22s %(message)s",
    )

    if args.ver_bitacora:
        from .decision import Bitacora
        for r in Bitacora(cfg.bitacora.ruta).leer_todo():
            print(f"{r['timestamp']}  {r['identificador']:<12} "
                  f"{r['resultado']:<28} {r['latencia_decision_ms']:>8.1f} ms  "
                  f"{r.get('clip') or ''}")
        return 0

    if args.mostrar_tuberia:
        from .buffer_circular import BufferCircular
        from .pipeline import PipelineAcceso
        buf = BufferCircular(cfg.clips.segundos_antes, cfg.codec.fps,
                             cfg.clips.max_buffers)
        print("gst-launch-1.0 -e \\\n  " +
              PipelineAcceso(cfg, buf).descripcion().replace(" t_", " \\\n  t_"))
        return 0

    from .servicio import ServicioAcceso
    return ServicioAcceso(cfg).ejecutar(dot_dir=args.dot)


if __name__ == "__main__":
    sys.exit(main())
