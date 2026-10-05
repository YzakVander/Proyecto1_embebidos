# D4 - Presupuesto de latencia (escrito ANTES de medir)

Ruta evaluada: fuente -> codificador -> RTP -> red. 1280x720 @ 30 fps.
Tubería del prototipo en la PC (x86, WSL2, GStreamer 1.24.2): `videotestsrc` y
`x264enc` por software. La tubería actual de la placa usa `v4l2src` (MJPEG),
`v4l2jpegdec`, `v4l2convert` y `v4l2h264enc` por hardware; su medición etapa
por etapa está pendiente (ver al final).

| Etapa | Estimado | Base del cálculo |
|---|---|---|
| Fuente (captura) | 33 ms | 1 cuadro a 30 fps |
| queue de entrada (8 buf) | 267 ms | 8 x 33 ms |
| queue de codificación (8 buf) | 267 ms | 8 x 33 ms |
| x264enc tune=zerolatency | 33 ms | sin reordenamiento de cuadros (sin B-frames) |
| h264parse | ~0 ms | no almacena |
| rtph264pay + udpsink | ~5 ms | empaquetado y envío |
| **Total estimado** | **~605 ms** | |

## MEDIDO (D1, tracer de GStreamer)

595 muestras de la ruta en 20 s (`D1-tracer.txt`). Latencia `videotestsrc -> udpsink`:

| Mínimo | Mediana | p99 | Máximo |
|---|---|---|---|
| 8.1 ms | 12.3 ms | 24.4 ms | 30.6 ms |

El rango típico es de 12 a 21 ms; el p99 es el que importa, porque lo que molesta
al vigilante es el peor caso.

## DIFERENCIA Y EXPLICACIÓN

Estimado 605 ms, medido ~17 ms. Factor 35x.

**Causa del error de estimación:** se asumió que un `queue` de 8 buffers
aporta siempre 8 x 33 ms. Es incorrecto: un `queue` solo aporta latencia
cuando está **lleno**. En régimen permanente, con el consumidor más rápido
que la fuente (30 fps), la cola se mantiene casi vacía y aporta el tiempo de
un buffer, no de su profundidad máxima.

La tabla de B3 describe el **peor caso** (cola saturada), no la operación
normal. La profundidad del `queue` define la latencia *máxima* bajo carga,
no la nominal.

**Presupuesto corregido (régimen permanente):**

| Etapa | Reparto estimado del total medido |
|---|---|
| Fuente + queues (no saturados) | ~5 ms |
| x264enc tune=zerolatency | ~8 ms |
| h264parse + rtph264pay + udpsink | ~4 ms |
| **Total** | **~17 ms** |

El tracer de esta corrida midió solo la ruta completa; el reparto por etapa es
una estimación. Lo medirá `d1-latencia.sh` por elemento.

**Pendiente:** repetir bajo carga (F6) para observar el peor caso y verificar
que la profundidad declarada acota la latencia como se espera.

**Pendiente en la placa:** `app/scripts/d1-latencia.sh` mide la aplicación real
con `GST_TRACERS="latency(flags=pipeline+element)"`, por ruta (fuente -> cada
sink) y por elemento, con mínimo, mediana, p99 y máximo
(`docs/guion-placa-rol-a.md`, paso 1.2). Fuera de la tubería quedan la captura de
la cámara, la red y el receptor, que suma 100 ms fijos de `rtpjitterbuffer`; eso
lo cubre la medición de extremo a extremo con cronómetro filmado (D2, paso 4.1).
