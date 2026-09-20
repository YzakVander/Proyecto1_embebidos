# A4 - Justificación de cada capsfilter

## capsfilter único: `video/x-raw,format=I420,width=1280,height=720,framerate=30/1`

**Qué restringe y por qué cada campo:**

| Campo | Razón |
|---|---|
| `format=I420` | Sin él, `videotestsrc` negocia `Y444_10LE` (4:4:4, 10 bits) y `x264enc` produce perfil `high-4:4:4`, que la mayoría de reproductores no decodifica y el codificador por hardware de la RPi 4 no acepta. Evidencia: `mediciones/A1-sin-formato.txt` vs `A1-con-formato.txt` |
| `width`/`height` | 1280x720 está dentro del tope de 1080p30 del bloque H.264 del BCM2711 (ítem C3) y cumple el ancho de banda previsto para RTP |
| `framerate=30/1` | RF-1 exige ≥15 fps; 30 da margen. Fija la base del cálculo de latencia por `queue` (ítem B3) |

**Por qué no se restringe más:** no se fija `colorimetry` ni `pixel-aspect-ratio`;
sobre-restringir impediría la negociación con fuentes que no los ofrezcan.

**Pendiente:** con cámara USB real (MJPEG/YUY2) habrá que añadir un
`videoconvert` explícito y, para la ruta por hardware, restringir el perfil
de salida del codificador a `main` o `constrained-baseline`.

---

# B2 - Decisión de leaky por rama

| Rama | Configuración | Justificación |
|---|---|---|
| Entrada (post-fuente) | `max-size-buffers=8 leaky=downstream` | Absorbe jitter de captura; si se satura es preferible perder un cuadro a bloquear la fuente en vivo |
| Codificación | `max-size-buffers=8 leaky=downstream` | Protege a la fuente del codificador. Evidencia de necesidad: `mediciones/B1-tee-queue.txt` (122 s vs 38 s) |
| **Grabación** | `queue` por omisión, **sin leaky** | La evidencia no se descarta. Profundidad por omisión para absorber el jitter de escritura a microSD |
| Red (RTP) | `max-size-buffers=8 leaky=downstream` | En transmisión en vivo un cuadro viejo no sirve; es preferible descartarlo a acumular latencia |
| Foto (JPEG) | `max-size-buffers=1 leaky=downstream` | Solo interesa el cuadro del instante del evento; profundidad mínima |

**Latencia aportada** (ver tabla del checklist, B3): 8 buffers a 30 fps = 267 ms;
1 buffer = 33 ms. La rama de grabación usa la profundidad por omisión, que
puede llegar a 1 s — aceptable porque no es la ruta de baja latencia.
