#!/usr/bin/env python3
"""Analiza el grafo .dot de la tuberia REAL (A1, A2, A5, A6, B1, B3).

El .dot lo genera la aplicacion misma (a6-grafo.sh), asi que describe lo que
GStreamer construyo de verdad, con la configuracion real: no lo que dice el
codigo. De ahi se extrae:

  A5/A6  inventario de elementos y conteo de conversores
  A1     caps negociados en cada frontera entre elementos
  A2     formato que llega al codificador
  B1     que hay inmediatamente despues de cada salida de cada tee
  B3     profundidad efectiva de cada queue y su latencia en el peor caso

Solo usa la biblioteca estandar: corre igual en la placa y en la PC.

Uso:  python3 analizar-dot.py grafos/acceso.dot
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict

# Valores por omision de queue (gst-inspect-1.0 queue). El .dot solo muestra
# las propiedades que difieren del valor por omision.
QUEUE_DEFECTO = {"max-size-buffers": 200, "max-size-bytes": 10485760,
                 "max-size-time": 1_000_000_000}

# Elementos que convierten o escalan video (A5). Se compara contra el tipo
# en minusculas, asi cubre videoconvert, videoscale, v4l2convert, etc.
CONVERSORES = ("convert", "scale", "videorate", "jpegdec")

# Campos de caps que se muestran en el resumen de cada frontera (A1)
CAMPOS_CAPS = ("format", "width", "height", "framerate", "stream-format",
               "alignment", "profile", "level")

RE_ELEMENTO = re.compile(
    r'subgraph cluster_(?P<id>\S+?_0x[0-9a-f]+) \{\s*'
    r'(?:[^{}]*?)label="(?P<label>(?:[^"\\]|\\.)*)";', re.S)
RE_ARISTA = re.compile(
    r'^\s*(?P<a>\S+?_0x[0-9a-f]+)_(?P<pa>[^\s]+?)_0x[0-9a-f]+ -> '
    r'(?P<b>\S+?_0x[0-9a-f]+)_(?P<pb>[^\s]+?)_0x[0-9a-f]+'
    r'(?: \[(?P<attrs>.*)\])?\s*$', re.M)


def leer(ruta: str):
    texto = open(ruta, encoding="utf-8", errors="replace").read()

    elementos = {}          # id -> (tipo, nombre, propiedades)
    for m in RE_ELEMENTO.finditer(texto):
        partes = m.group("label").split("\\n")
        if len(partes) < 2 or not partes[0][:1].isalpha():
            continue
        if m.group("id").endswith(("_sink", "_src")) or "_0x" not in m.group("id"):
            continue
        props = {}
        for p in partes[3:]:
            if "=" in p:
                k, v = p.split("=", 1)
                props[k.strip()] = v.strip()
        elementos[m.group("id")] = (partes[0], partes[1], props)

    aristas = []            # (id_a, pad_a, id_b, pad_b, caps)
    for m in RE_ARISTA.finditer(texto):
        attrs = m.group("attrs") or ""
        if 'style="invis"' in attrs:
            continue        # union interna sink->src de un mismo elemento
        caps = None
        c = re.search(r'label="((?:[^"\\]|\\.)*)"', attrs)
        if c:
            caps = c.group(1)
        aristas.append((m.group("a"), m.group("pa"), m.group("b"), m.group("pb"), caps))
    return elementos, aristas


def resumir_caps(caps: str | None) -> str:
    if not caps:
        return "(sin caps: el elemento no llego a negociar)"
    lineas = [l.strip() for l in caps.split("\\l") if l.strip()]
    if not lineas:
        return "(caps vacios)"
    campos = []
    for l in lineas[1:]:
        if ":" in l:
            k, v = l.split(":", 1)
            if k.strip() in CAMPOS_CAPS:
                campos.append(f"{k.strip()}={v.strip()}")
    return lineas[0] + (", " + ", ".join(campos) if campos else "")


def nombre(elementos, ident: str) -> str:
    e = elementos.get(ident)
    return f"{e[1]} ({e[0]})" if e else ident.rsplit("_0x", 1)[0]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    elementos, aristas = leer(sys.argv[1])

    # ------------------------------------------------------------------ A5/A6
    print("== A5/A6: inventario del grafo real ==")
    tipos = Counter(t for t, _, _ in elementos.values())
    for tipo, n in sorted(tipos.items()):
        print(f"  {n:2d} {tipo}")
    conv = [(t, n) for t, n, _ in elementos.values()
            if any(c in t.lower() for c in CONVERSORES)]
    print(f"\n  Conversores y decodificadores: {len(conv)}")
    for t, n in conv:
        print(f"    {n} ({t})")

    # ------------------------------------------------------------------ A1/A2
    # Orden del flujo: recorrido en profundidad desde las fuentes, rama por
    # rama, en vez del orden (casi inverso) en que GStreamer escribe el .dot.
    salientes = defaultdict(list)
    entrantes = set()
    for arista in aristas:
        salientes[arista[0]].append(arista)
        entrantes.add(arista[2])
    ordenadas, vistos = [], set()

    def recorrer(ident: str) -> None:
        for arista in sorted(salientes[ident], key=lambda x: x[1]):
            if id(arista) in vistos:
                continue
            vistos.add(id(arista))
            ordenadas.append(arista)
            recorrer(arista[2])

    # Primero las fuentes de verdad (v4l2src, videotestsrc); despues los
    # elementos internos de un bin cuya entrada no aparece como arista.
    fuentes = [a for a in salientes if a not in entrantes]
    fuentes.sort(key=lambda a: not elementos.get(a, ('',))[0].endswith('Src'))
    for fuente in fuentes:
        recorrer(fuente)
    ordenadas += [x for x in aristas if id(x) not in vistos]

    print("\n== A1: caps negociados en cada frontera (en orden del flujo) ==")
    for a, pa, b, pb, caps in ordenadas:
        if caps is None:
            continue
        print(f"  {nombre(elementos, a)}:{pa} -> {nombre(elementos, b)}:{pb}")
        print(f"      {resumir_caps(caps)}")

    print("\n== A2: lo que llega a cada codificador ==")
    hay = False
    for a, pa, b, pb, caps in aristas:
        tipo_b = elementos.get(b, ("", "", {}))[0].lower()
        if "enc" in tipo_b and "parse" not in tipo_b:
            hay = True
            print(f"  {nombre(elementos, a)} -> {nombre(elementos, b)}")
            print(f"      {resumir_caps(caps)}")
    if not hay:
        print("  (no se encontro ningun codificador en el grafo)")

    # ------------------------------------------------------------------ B1
    print("\n== B1: que sigue a cada salida de tee ==")
    salidas = defaultdict(list)
    for a, pa, b, pb, _ in aristas:
        if elementos.get(a, ("",))[0] == "GstTee":
            salidas[a].append(b)
    for tee, destinos in salidas.items():
        print(f"  {nombre(elementos, tee)}: {len(destinos)} salidas")
        for d in destinos:
            tipo = elementos.get(d, ("?",))[0]
            marca = "OK" if tipo == "GstQueue" else "SIN QUEUE"
            print(f"    -> {nombre(elementos, d)}  [{marca}]")

    # ------------------------------------------------------------------ B3
    fps = 30.0
    for _, _, _, _, caps in aristas:
        m = re.search(r"framerate: (\d+)/(\d+)", caps or "")
        if m and int(m.group(2)):
            fps = int(m.group(1)) / int(m.group(2))
            break
    print(f"\n== B3: profundidad efectiva de cada queue (peor caso a {fps:g} fps) ==")
    print("  (las propiedades sin '*' son las declaradas; '*' = valor por omision)")
    for ident, (tipo, nom, props) in sorted(elementos.items(), key=lambda x: x[1][1]):
        if tipo != "GstQueue":
            continue
        ef = {}
        for k, defecto in QUEUE_DEFECTO.items():
            ef[k] = (int(props[k]), "") if k in props else (defecto, "*")
        topes = []
        if ef["max-size-buffers"][0]:
            topes.append(ef["max-size-buffers"][0] / fps * 1000)
        if ef["max-size-time"][0]:
            topes.append(ef["max-size-time"][0] / 1e6)
        peor = f"{min(topes):.0f} ms" if topes else "sin tope de tiempo ni de buffers"
        leaky = props.get("leaky", "no")
        print(f"  {nom:<18} buffers={ef['max-size-buffers'][0]}{ef['max-size-buffers'][1]} "
              f"bytes={ef['max-size-bytes'][0]}{ef['max-size-bytes'][1]} "
              f"time={ef['max-size-time'][0] / 1e9:g}s{ef['max-size-time'][1]} "
              f"leaky={leaky} -> peor caso {peor}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
