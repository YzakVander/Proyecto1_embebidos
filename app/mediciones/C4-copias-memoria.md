# C4 — Copias entre dominios de memoria

**Ítem del acta:** *Se revisó si hay copias evitables entre dominios de
memoria (`capture-io-mode=dmabuf` donde aplique).*

Este documento recorre cada frontera de la tubería por donde pasa un cuadro,
dice qué se copia y cuánto pesa, y clasifica cada copia como **inevitable**
(con su razón), **evitable** (con la propuesta) o **pendiente de medir**.

Tasas: 1280×720 a 30 fps. Un cuadro I420 pesa 1280·720·1.5 = **1.38 MB**; uno
BGR, 1280·720·3 = **2.76 MB**; uno H.264, ~10 KB (17.4 MB/min medidos por el
Rol B ÷ 1800 cuadros/min).

---

## 1. Dominios de memoria

| Dominio | Quién lo usa |
|---|---|
| Búferes del driver `uvcvideo` | `v4l2src`: el USB deposita ahí el MJPEG de la cámara |
| Bloque `bcm2835-codec` (VideoCore) | `v4l2jpegdec`, `v4l2convert` y `v4l2h264enc`: son el **mismo** bloque de hardware (`/dev/video10, 11, 12…`, `C1-hallazgo-contextos.txt`) |
| Memoria de GStreamer (CPU) | `h264parse`, `splitmuxsink`, `rtph264pay`, los appsink |
| Memoria de Python | la deque del búfer circular y los arreglos de NumPy del lector QR |

---

## 2. Fronteras y copias

### Rama de codificación (30 fps)

| # | Frontera | Qué cruza | Peso por segundo | Clasificación |
|---|---|---|---|---|
| 1 | `v4l2src` → `v4l2jpegdec` | MJPEG comprimido | ~100–200 KB × 30 | **Pendiente de medir.** Dos drivers distintos (USB y VideoCore): compartir el búfer exige `dmabuf`. El volumen es bajo porque el JPEG va comprimido |
| 2 | `v4l2jpegdec` → `v4l2convert` | video crudo | 1.38 MB × 30 = **41 MB/s** | **Pendiente de medir.** Mismo bloque de hardware: es la frontera donde `dmabuf` más podría ahorrar |
| 3 | `v4l2convert` → `v4l2h264enc` | video crudo | **41 MB/s** | **Pendiente de medir**, igual que la 2. Además, `v4l2convert` podría sobrar en esta rama (§3.2) |
| 4 | `v4l2h264enc` → `h264parse` | H.264 | ~10 KB × 30 = 0.3 MB/s | **Inevitable.** El flujo comprimido tiene que salir del bloque hacia la CPU para empaquetarse (MP4, RTP). El volumen es despreciable |

### Rama de clips (30 fps)

| # | Frontera | Qué cruza | Peso por segundo | Clasificación |
|---|---|---|---|---|
| 5 | appsink → deque (`bytes(info.data)`) | H.264 | 0.3 MB/s | **Inevitable.** El búfer de GStreamer se libera en el `unmap`; el cuadro tiene que vivir 10 s en la deque. Medido en B5: p99 de 0.6 ms por cuadro en la PC |

### Rama de QR (30 fps de entrada, 5 análisis/s)

| # | Frontera | Qué cruza | Peso por segundo | Clasificación |
|---|---|---|---|---|
| 6 | `v4l2src` → `v4l2jpegdec` (segundo decodificador) | MJPEG | igual que la 1 | **Evitable** (§3.2): el JPEG ya se decodifica en la otra rama |
| 7 | `v4l2jpegdec` → `v4l2convert` | video crudo | 41 MB/s | **Evitable** junto con la 6 |
| 8 | appsink → NumPy (`.copy()`) | BGR | 2.76 MB × **30** = **83 MB/s** | **Inevitable por cuadro, evitable en cantidad** (§3.1) |

---

## 3. Copias evitables

### 3.1 La rama de QR copia 30 cuadros por segundo y analiza 5

El callback del appsink de QR (`pipeline.py`, `_copiar_cuadro_qr`) copia
**cada** cuadro a un arreglo de NumPy y se lo entrega al lector, que lo guarda
reemplazando al anterior (`lector_qr.py`, `entregar_cuadro`). El lector toma
uno cada 0.2 s (`periodo_s`). De cada 6 cuadros copiados, 5 se descartan sin
analizarse.

- **Por qué la copia en sí es inevitable:** `np.frombuffer` apunta a memoria
  de GStreamer que se libera en el `unmap`; sin `.copy()` el hilo del lector
  leería memoria liberada.
- **Por qué la cantidad es evitable:** basta con copiar solo cuando el lector
  va a necesitar un cuadro nuevo. Se copia uno cada **medio periodo** del
  lector (0.1 s): el doble de lo que consume, para que al despertar siempre
  encuentre un cuadro fresco aunque su reloj y la llegada de los cuadros no
  coincidan. Como los cuadros llegan cada 33 ms, el efecto real es de 7 a 10
  copias por segundo: de **83 MB/s a ~23–28 MB/s** de memcpy en el hilo de
  streaming.
- **Por qué no se resuelve con `videorate` en la tubería:** su restricción de
  tasa se propagaría hacia arriba por `t_raw` y chocaría con la rama del
  codificador (`not-negotiated`, documentado en `pipeline.py`).
- **Estado: implementado** (`pipeline.py`, `_copiar_cuadro_qr`). La muestra
  se sigue sacando del appsink en cada cuadro (un appsink con muestras sin
  leer retiene el EOS); lo que se evita es el `map` y la copia.
- **Medido en la PC** (x86, `videoconvert` en lugar de `v4l2convert`, 10 s,
  con un lector falso que cuenta las entregas):

  | | Cuadros copiados al lector | Callback `qr` p50 | p99 |
  |---|---|---|---|
  | Antes | 30.0 por segundo | 0.92 ms | 2.28 ms |
  | Después | 8.4 por segundo | 0.08 ms | 1.49 ms |

  El p50 baja porque la mayoría de las invocaciones ya no copian; el p99
  sigue reflejando el costo de una copia. **Pendiente (placa):** el mismo
  cronómetro de B5 con BGR real de `v4l2convert` en el Cortex-A72.

### 3.2 El JPEG se decodifica dos veces

`t_raw` reparte el MJPEG **sin decodificar**, así que cada rama lleva su propio
`v4l2jpegdec ! v4l2convert`. El Rol B contó **cinco contextos simultáneos**
del bloque `bcm2835-codec` (`C1-hallazgo-contextos.txt`):

    rama de codificación : v4l2jpegdec + v4l2convert + v4l2h264enc
    rama de QR           : v4l2jpegdec + v4l2convert

**Alternativa:** decodificar una sola vez antes del tee.

    v4l2src ! image/jpeg ! v4l2jpegdec ! queue ! tee name=t_raw
      t_raw. ! queue ! v4l2h264enc ...                     (codificación)
      t_raw. ! queue ! v4l2convert ! video/x-raw,format=BGR ! appsink   (QR)

- Ahorra una decodificación JPEG completa por cuadro (30 por segundo) y baja
  de 5 a **3 contextos** (o 4, si la rama del codificador necesita su
  `v4l2convert`).
- En la rama del codificador, `v4l2convert` podría sobrar: el codificador
  acepta YU12 (I420) y NV12 directamente (`C1-hardware-rpi4.txt`). Depende del
  formato que entregue `v4l2jpegdec`, que se lee en el `.dot` de A6.
- **Riesgo:** cambia la negociación de caps de `t_raw` (ahora video crudo en
  vez de MJPEG), y las queues de 8 cuadros de esa zona pasarían a guardar
  video crudo: hasta 8 × 1.38 MB = 11 MB por queue.
- **Estado:** propuesta, no implementada. Solo se puede validar en la placa.

### 3.3 `dmabuf` entre los elementos V4L2

Las fronteras 1, 2 y 3 son las que `capture-io-mode=dmabuf` /
`output-io-mode=dmabuf-import` podrían convertir en cero copias, compartiendo
descriptores en lugar de copiar 41 MB/s por frontera.

- El Rol B probó `io-mode` mmap, dmabuf y dmabuf-import y **fallaron**
  (`C1-hallazgo-contextos.txt`), pero en esa prueba fallaba **cualquier**
  `gst-launch` externo por el límite de contextos con el servicio corriendo
  (`ret -3`). El resultado no distingue entre "dmabuf no funciona" y "el
  bloque estaba ocupado".
- **Estado:** pendiente de medir en la placa con el servicio detenido.
  Criterio del acta: si no mejora la CPU, queda documentado como
  "probado y descartado" en vez de activarse sin evidencia.

---

## 4. Resumen

| Copia | Clasificación | Acción |
|---|---|---|
| H.264 del codificador a la CPU (4) | Inevitable | — |
| H.264 a la deque de clips (5) | Inevitable | — |
| BGR a NumPy en la rama QR (8) | Inevitable por cuadro | **Implementado:** ~8 copias por segundo en vez de 30 (§3.1) |
| Segunda decodificación JPEG (6, 7) | Evitable | **Decodificar una vez antes del tee** (§3.2), probar en la placa |
| Video crudo entre elementos V4L2 (1, 2, 3) | Pendiente | **Probar `dmabuf` con el servicio detenido** (§3.3) |
