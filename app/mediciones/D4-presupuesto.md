# D4 - Presupuesto de latencia (escrito ANTES de medir)

Ruta evaluada: fuente -> codificador -> RTP -> red. 1280x720 @ 30 fps.

| Etapa | Estimado | Base del cálculo |
|---|---|---|
| Fuente (captura) | 33 ms | 1 cuadro a 30 fps |
| queue de entrada (8 buf) | 267 ms | 8 x 33 ms |
| queue de codificación (8 buf) | 267 ms | 8 x 33 ms |
| x264enc tune=zerolatency | 33 ms | sin reordenamiento de cuadros (sin B-frames) |
| h264parse | ~0 ms | no almacena |
| rtph264pay + udpsink | ~5 ms | empaquetado y envío |
| **Total estimado** | **~605 ms** | |

MEDIDO: (pendiente)
DIFERENCIA: (pendiente)

## MEDIDO (D1, tracer de GStreamer)

602 muestras en 20 s. Latencia videotestsrc -> udpsink: **12 a 21 ms**.

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

| Etapa | Real |
|---|---|
| Fuente + queues (no saturados) | ~5 ms |
| x264enc tune=zerolatency | ~8 ms |
| h264parse + rtph264pay + udpsink | ~4 ms |
| **Total** | **~17 ms** |

**Pendiente:** repetir bajo carga (F6) para observar el peor caso y verificar
que la profundidad declarada acota la latencia como se espera.
