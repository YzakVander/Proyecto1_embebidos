# A2 / A4 / B2 / B3 / C3 / D3 — Justificación de la tubería vigente

Tubería de `app/acceso/pipeline.py` con `app/config/acceso.conf` (cámara USB
UVC en MJPEG, codificador por hardware del BCM2711). Para regenerar la
descripción exacta sin transcribirla a mano:

    python3 -m acceso -c config/acceso.conf --mostrar-tuberia

```
v4l2src ─ image/jpeg ─ queue(8,leaky) ─ t_raw ─┬─ queue(8,leaky) ─ v4l2jpegdec ─ v4l2convert ─ v4l2h264enc ─ level=4 ─ h264parse ─ t_h264 ─┬─ queue(1 s) ─ splitmuxsink           (grabación)
                                               │                                                                                         ├─ queue(8,leaky) ─ rtph264pay ─ udpsink (streaming)
                                               │                                                                                         └─ queue(8,leaky) ─ h264parse ─ byte-stream ─ appsink (clips)
                                               └─ queue(1,leaky) ─ v4l2jpegdec ─ v4l2convert ─ BGR ─ appsink                                         (QR)
```

> Este documento reemplaza la versión del 2026-09-19, que justificaba un
> capsfilter `video/x-raw,format=I420` y una rama "Foto (JPEG)" de la
> tubería de desarrollo con `videotestsrc` y `x264enc`. Esa tubería ya no
> existe; las mediciones `A1-*.txt` siguen siendo válidas como evidencia del
> hallazgo de negociación, pero no describen el sistema actual.

---

## A2 — Formato que entrega la cadena y formato que acepta el codificador

El acta advierte que el codificador de la RPi 4 "solo acepta NV12" y que,
si la fuente entrega otra cosa, hay un `videoconvert` escondido consumiendo
CPU. **En este bloque esa premisa no se cumple.** El codificador
`bcm2835-codec` (`/dev/video11`) acepta 14 formatos de entrada, medido por el
Rol B con `v4l2-ctl --list-formats-out` (`C1-hardware-rpi4.txt`):

    YU12 (I420)  YV12  NV12  NV21  RGBP  RGB3  BGR3  AB24  BGR4
    YUYV  YVYU  UYVY  VYUY  NC12

La cadena real es `v4l2jpegdec ! v4l2convert ! v4l2h264enc`: la conversión de
formato, si hace falta, la hace `v4l2convert` sobre el ISP de hardware
(`bcm2835-isp`), no un `videoconvert` por software. Por construcción no hay
conversión por CPU en la rama del codificador; A5 lo verifica sobre el grafo
real.

**Pendiente (placa):** leer en el `.dot` de la aplicación (`--dot`) qué
formato negocian efectivamente `v4l2jpegdec → v4l2convert` y
`v4l2convert → v4l2h264enc`. Si `v4l2jpegdec` ya entrega un formato que el
codificador acepta (I420 o NV12), `v4l2convert` en esa rama podría ser
prescindible: un contexto menos del bloque (ver C4).

---

## A4 — Justificación de cada capsfilter

La tubería tiene cuatro capsfilter. Para cada uno: qué fija cada campo, y por
qué no se fija nada más.

### 1. Fuente: `image/jpeg,width=1280,height=720,framerate=30/1`

| Campo | Razón |
|---|---|
| `image/jpeg` | La cámara UVC entrega el video comprimido en MJPEG. Sin comprimir (YUY2), 1280×720 a 30 fps son 1280·720·2·30 ≈ 55 MB/s, más de lo que el USB 2.0 sostiene en la práctica (~35–40 MB/s). Por eso las cámaras UVC suelen ofrecer YUY2 a 720p solo a 5–10 fps. **Pendiente (placa):** confirmar con `v4l2-ctl -d /dev/video0 --list-formats-ext` los modos que ofrece esta cámara. |
| `width=1280,height=720` | Dentro del tope de 1080p30 del bloque H.264 del BCM2711 (ver C3). Suficiente para reconocer a una persona en la entrada y para leer un QR ocupando ≥25 % del alto (RF-12). |
| `framerate=30/1` | RF-1 exige ≥15 fps: 30 da margen al doble. Es también la base de las profundidades de B3 y del GOP de D3. **Cuidado:** este campo fija la tasa *pedida*, no la *real*. La cámara la baja sola con exposiciones largas (ver `acceso.conf`, `exposure_time_absolute=2000`); por eso A3 cuenta cuadros en lugar de leer caps. |

**Por qué no se restringe más:** no se fija `pixel-aspect-ratio` ni
`colorimetry`. La cámara los ofrece por su cuenta, y fijarlos solo podría
impedir la negociación si un reemplazo de la cámara reporta otro valor.

### 2. Salida del codificador: `video/x-h264,level=(string)4`

| Campo | Razón |
|---|---|
| `level=(string)4` | El nivel 4 de H.264 cubre hasta 1920×1080 a 30 fps, así que 720p30 está holgado. El filtro **coincide con el hardware**: el nivel por omisión del codificador ya es 4 (`h264_level default=11 (4)`, `C1-hardware-rpi4.txt`), y los segmentos grabados en la placa salen con nivel 4.0 (`A3-fps-rpi4.txt`). Declararlo deja escrito el nivel con que el flujo se anuncia a `h264parse`, `mp4mux` y al receptor, en vez de depender de lo que cada lado deduzca en la negociación. **Opcional (placa):** quitarlo una vez y anotar qué pasa. |

**Por qué no se fija el perfil:** el perfil que importa a los consumidores
(VLC, `avdec_h264` en el puesto de vigilancia, `mp4mux`) es cualquiera
estándar de 8 bits 4:2:0. **Medido:** los segmentos grabados salen en perfil
**Baseline**, aunque el perfil por omisión del control del codificador es
High (`C1-hardware-rpi4.txt`). El perfil efectivo lo fija la negociación de
caps de `v4l2h264enc`, no el valor por omisión del control. Baseline es el
más compatible y no usa cuadros B, lo que conviene a la latencia; a cambio
comprime algo peor que High a igual calidad. No se fija `profile=` porque el
resultado actual ya sirve, y restringirlo solo agrega una forma de fallar.

### 3. Antes del appsink de clips: `video/x-h264,stream-format=byte-stream,alignment=au`

| Campo | Razón |
|---|---|
| `stream-format=byte-stream` | Sin este campo, `h264parse` entrega formato `avc` (cada NAL con prefijo de longitud). El buffer circular guarda bytes crudos y el clip se rearma después con otro `h264parse`, que espera códigos de inicio `00 00 00 01`. **Verificado con `xxd`:** un clip generado sin esta línea empezaba en `00 00 00 02` y no se podía releer (`B4-B5-buffer-circular.txt`, hallazgo 2). |
| `alignment=au` | Un cuadro completo por buffer. Así cada elemento de la deque es un cuadro, con su PTS y su bandera de cuadro clave, lo que permite recortar en un IDR. |

**Por qué hace falta un segundo `h264parse` en esta rama:** un `tee` impone
las mismas caps a todas sus ramas. Si este capsfilter colgara directo de
`t_h264`, la restricción `byte-stream` subiría por el tee hasta las ramas de
grabación y streaming, y la negociación fallaría con `not-negotiated`
(`B4-B5-buffer-circular.txt`, hallazgo 1). El `h264parse` propio convierte
solo en esta rama.

### 4. Rama de QR: `video/x-raw,format=BGR`

| Campo | Razón |
|---|---|
| `format=BGR` | Es el formato nativo de OpenCV. Pedirlo aquí hace que la conversión la haga `v4l2convert` (ISP de hardware) y no Python con `cv2.cvtColor` en cada cuadro. |

**Por qué no se fijan ancho, alto ni tasa:** ambos propagarían su restricción
hacia arriba por `t_raw` y chocarían con la rama del codificador. La
reducción a 640 px la hace `cv2.resize` en el hilo del lector, y la tasa de 5
análisis/s la impone el lector descartando cuadros por tiempo. Es más barato
que arriesgar un `not-negotiated`.

---

## B2 — Decisión de leaky por rama

| Rama | Configuración | ¿Puede perder cuadros? | Justificación |
|---|---|---|---|
| Entrada (antes de `t_raw`) | `max-size-buffers=8 leaky=downstream` | Sí | La fuente es en vivo: si se bloquea, la cámara descarta cuadros de todos modos, pero sin control. Es preferible perder un cuadro aquí a frenar el `v4l2src`. |
| Codificación | `max-size-buffers=8 leaky=downstream` | Sí | Protege a la fuente de un codificador momentáneamente lento. La necesidad de una queue por salida de tee está medida: 122 s contra 38 s para 150 cuadros sin y con queue (`B1-tee-queue.txt`). |
| **Grabación** | `max-size-time=1 s`, **sin leaky** | **No** | Es la evidencia. Un cuadro descartado aquí es un hueco en el video que se entrega como prueba. 1 s de profundidad absorbe el jitter de escritura a la microSD (ver B3). |
| Streaming RTP | `max-size-buffers=8 leaky=downstream` | Sí | En vivo, un cuadro viejo no sirve: es preferible descartarlo a acumular latencia frente al vigilante. |
| Clips (appsink) | `max-size-buffers=8 leaky=downstream` + appsink `max-buffers=600 drop=true` | Sí, **con tensión explícita** | Ver nota abajo. |
| QR (appsink) | `max-size-buffers=1 leaky=downstream` + appsink `max-buffers=1 drop=true` | Sí, por diseño | Si el detector se atrasa, interesa el presente: un QR de hace dos segundos ya no sirve. Un solo buffer garantiza que el lector siempre analiza el cuadro más reciente. |

**La tensión de la rama de clips.** Esta rama alimenta el buffer circular del
que salen los clips de cada evento, que son evidencia, y aun así puede
descartar cuadros. Es una decisión consciente: el callback del appsink solo
copia bytes a una deque (B5), así que en operación normal la cola no se
llena. Si alguna vez se llenara, el clip perdería algunos cuadros, pero la
tubería entera (grabación continua y streaming incluidos) no se bloquearía.
La evidencia completa sigue existiendo en la grabación continua, que no
descarta. Un clip con un hueco se puede reconstruir desde la grabación; una
tubería bloqueada no graba nada.

---

## B3 — Latencia que aporta cada queue

Profundidad declarada en todas las queues (desde el 2026-10-02 también en la
de grabación, que antes heredaba los valores por omisión sin decirlo).

| Queue | Profundidad declarada | Peor caso a 30 fps |
|---|---|---|
| Entrada | 8 buffers | 267 ms |
| Codificación | 8 buffers | 267 ms |
| Grabación | 1 s (`max-size-time=1000000000`, sin límite de buffers ni bytes) | 1000 ms |
| Streaming RTP | 8 buffers | 267 ms |
| Clips | 8 buffers | 267 ms |
| QR | 1 buffer | 33 ms |

**Ruta de baja latencia (cámara → vigilante):** entrada + codificación +
streaming = 801 ms en el peor caso, con las tres colas llenas. En régimen
permanente las colas están casi vacías y aportan mucho menos: esa diferencia
está medida y explicada en `D4-presupuesto.md`. La profundidad define la
latencia *máxima* bajo carga, no la nominal.

**Grabación: por qué 1 s.** Son los mismos valores que la queue aplicaría por
omisión (200 buffers, 10 MB o 1 s, lo primero que se alcance; a 30 fps con
H.264 el tope de tiempo llega primero). Se declararon para convertir una
omisión en una decisión. La grabación no está en la ruta del vigilante, así
que su latencia no importa; lo que importa es no perder cuadros cuando la
microSD tarda en una escritura.

**Pendiente (Rol B, F5):** con la tasa de escritura medida en la placa
(~17.4 MB/min, es decir ~0.3 MB/s), comprobar con `iostat -x 5` la latencia
de escritura de la microSD. Si nunca se acerca a 1 s, la profundidad se puede
bajar; si se acerca, 1 s está bien elegido.

---

## C3 — Límites del bloque de codificación

| | Píxeles por segundo | Uso del bloque |
|---|---|---|
| Tope del H.264 del BCM2711 (1080p30) | 1920·1080·30 ≈ 62.2 Mpx/s | 100 % |
| Configuración actual (720p30) | 1280·720·30 ≈ 27.6 Mpx/s | **44 %** |

Margen de ~2.25×. Duplicar la resolución a 2560×1440 (110.6 Mpx/s) se sale del
bloque: esa sería la primera etapa en romperse si se duplica la resolución.
**Pendiente:** confirmar con C2 (CPU con codificador por hardware y por
software) y con F5 (disco) que ninguna otra etapa se rompe antes.

---

## D3 — Intervalo de cuadros clave

`h264_i_frame_period=30` con `fps=30` → un cuadro clave cada **1.00 s**
(declarado en `acceso.conf`, sección `[codec]`, y en `gop = 30`).

**Por qué 30 y no otro valor.** Un vigilante que abre el receptor, o que
pierde paquetes, no puede mostrar imagen hasta el siguiente cuadro clave. Con
GOP 30 a 30 fps espera como máximo 1 s, que es lo que fija RNF-2. Un GOP de 15
bajaría la espera a 0.5 s a costa de más bits por segundo en cuadros clave a
igual calidad; un GOP de 60 la subiría a 2 s. Para un vigilante que decide un
acceso en un plazo de 30 s, 1 s de espera inicial es aceptable, y el costo en
ancho de banda es moderado.

**El GOP también fija la precisión de los clips.** El buffer circular recorta en
un cuadro clave, así que un clip puede empezar hasta 1 s antes de lo pedido
(medido: 10.47 s en lugar de 10 s, `B4-B5-buffer-circular.txt`).

**Dos mecanismos para el mismo problema.** El cliente que se conecta tarde
necesita, además del cuadro clave, los parámetros SPS/PPS para decodificarlo.
`repeat_sequence_header=1` (en el codificador) y `config-interval=-1` (en
`h264parse`) los reinsertan en cada cuadro clave. Sin ellos, el GOP corto no
serviría: el cliente recibiría cuadros clave que no puede decodificar.

**Medido en la placa** (3 segmentos de 59 s grabados el 2026-10-02 y
extraídos con `recolectar-evidencia.sh`; detalle en `A3-fps-rpi4.txt`):

| Intervalo entre cuadros clave | Veces |
|---|---|
| 1.012 s | 29 |
| 1.008 s | 28 |
| ~0.40 s (irregular) | 1 por segmento |

Cuadro clave cada 30 cuadros, a la tasa real de 29.70 fps → **1.01 s**: el
codificador aplica el valor configurado. Cumple RNF-2 (≤ 1 s de espera, con
la tolerancia que impone la tasa real de la cámara).

**El cuadro clave irregular.** Aparece uno por segmento, y su posición se
corre ~1 s de un segmento al siguiente (t = 2.42 s, 3.44 s, 4.48 s). Es
consistente con un cuadro clave forzado por `splitmuxsink`
(`send-keyframe-requests=true`), que lo pide en una grilla de 60 s mientras
los segmentos se cortan cada ~59 s. Es inofensivo: un IDR extra por minuto.
No está verificado.

**Por qué no sirve `v4l2-ctl --get-ctrl`.** Cada apertura de `/dev/video11`
es un contexto independiente del bloque: consultarlo desde otro proceso
muestra los valores por omisión (60), no los que fijó la aplicación. La
verificación válida es la del archivo grabado:

    ffprobe -v error -select_streams v -show_entries packet=pts_time,flags \
        -of csv=p=0 evidencia_00027.mp4 | grep K | head
