# Bitácora individual de trabajo

**Estudiante:** Daniel Chavarría García
**Rol en el equipo:** B — Plataforma (Yocto, BSP, imagen) · asumió temporalmente el Rol A mientras el compañero no tuvo disponibilidad
**Proyecto 1 — Sistema de control de acceso con Yocto Project y GStreamer**
**Taller de Sistemas Embebidos · TEC · II Semestre 2026**
**Prof. Dr. Ing. Johan Carvajal Godínez**

---

## Entorno de trabajo

### Fase 1 (10–23 de septiembre)

| Elemento | Valor |
|---|---|
| Host | WSL2 · Ubuntu 24.04 sobre Windows (DESKTOP-R72NF1I) |
| RAM / swap | 7.6 GiB / 8 GiB |
| GStreamer en el host | 1.24.2 |

### Fase 2 (24 de septiembre en adelante) — migración a Linux nativo

| Elemento | Valor |
|---|---|
| Host | **Ubuntu 26.04 nativo** (partición propia, daniel-X510UQ) |
| Yocto | Poky / oe-core `wrynose`, DISTRO_VERSION 6.0.3 |
| BitBake | 2.18.0 (rama `2.18`, no `wrynose`) |
| Máquina destino | `raspberrypi4-64` (`TUNE_FEATURES = aarch64 crc cortexa72 nocrypto`) |
| GStreamer host / imagen | **1.28.2 / 1.28.5** |
| Python / OpenCV en la imagen | **3.14 / 4.13.0** |
| Cámara de desarrollo | USB DV20 en `/dev/video2` (MJPEG 1280×720@30) |
| Repositorio | `github.com/YzakVander/Proyecto1_embebidos`, rama `Daniel` |
| Hardware destino | RPi4 y microSD del **laboratorio**, rotativas entre sesiones; sin teclado, sin cable de red propio, sin adaptador UART |

**Motivo de la migración:** WSL2 no expone cámaras V4L2 ni recibe UDP sin
reenvío de puertos. Como el puesto de vigilancia debe *recibir* la
transmisión, Linux nativo era necesario. Beneficio adicional: el GStreamer
del host pasó a coincidir con el de la imagen.

---

## Registro de decisiones de diseño

| # | Fecha | Decisión | Alternativas consideradas | Justificación |
|---|---|---|---|---|
| D-01 | 09-10 | `DISTRO = "poky"` | Build distro-less | meta-raspberrypi declara Poky como su foco de pruebas |
| D-02 | 09-10 | `INIT_MANAGER = "systemd"` | sysvinit | Arranque automático y reinicio ante falla con una unidad; el cierre ordenado del MP4 requiere `TimeoutStopSec` |
| D-03 | 09-10 | Capas por enlace simbólico | Clonar árbol nuevo | Evita duplicar ~2 GiB |
| D-04 | 09-10 | Aceptar `synaptics-killswitch` | Excluir `packagegroup-base-extended` | `core-image-base` arrastra el firmware WiFi por diseño |
| D-05 | 09-10 | Cámara USB (UVC) con `v4l2src` | CSI con `libcamerasrc` | Autorizado por el profesor; elimina el riesgo técnico más alto |
| D-06 | 09-10 | Plugins completos en la 1.ª iteración | Subpaquetes desde el inicio | Primero funcionar, después afinar |
| D-07 | 09-10 | Compilar en casa, verificar en laboratorio | QEMU para todo | Acceso intermitente a la RPi4 |
| D-08 | 09-19 | `appsink` con búfer circular de pre-evento | `split-now`; cuadro único | El clip necesita contexto ANTES del evento |
| D-09 | 09-19 | Cuadros H.264 comprimidos, no crudos | I420 en RAM | 10 s = 235 KiB medidos, contra ~415 MB crudos |
| D-10 | 09-19 | Ventana del clip: 5 s antes + 5 s después | 3+2 | Con cuadros comprimidos el costo en RAM es irrelevante |
| D-11 | 09-19 | Reconectar con alerta, no morir | Morir y que systemd reinicie | Reintentos indefinidos cada 5 s |
| D-12 | 09-19 | Plazo de 30 s, vencimiento DEFINITIVO | 5 s, 10 s | 30 s da margen a una persona real; el vencimiento cierra la solicitud |
| D-13 | 09-19 | Bitácora JSONL con `fsync` | journald | Se inspecciona con `cat`; `fsync` la protege de corte de energía |
| D-14 | 09-19 | Dos LED indicadores (GPIO 27 permitido, 22 denegado) | Relé y cerradura física | No hay cerradura disponible; el indicador no es elemento de seguridad física |
| **D-15** | **09-23** | **Packagegroup desglosado a subpaquetes derivados de la tubería real** | Conjuntos completos `-good`/`-bad` | La lista **no se adivinó**: se mapeó cada elemento a su biblioteca con `gst-inspect-1.0 \| grep Filename`, y de ahí al subpaquete |
| **D-16** | **09-23** | **`videotestsrc` y herramientas en `-diagnostico`, fuera del núcleo** | Un solo paquete con todo | La imagen de producción no lleva la fuente de prueba de desarrollo |
| **D-17** | **09-23** | **SSH (dropbear) en la imagen** | Imagen sin acceso remoto | Permite iterar el código con `scp` + `systemctl restart` sin regenerar la imagen. **Decisión clave**: sin SSH cada ajuste habría costado horas |
| **D-18** | **09-23** | **Instalación manual en `do_install`** | `inherit setuptools3` | Ocho módulos sin dependencias de compilación; `setuptools3` agregaría `python3-setuptools-native` sin aportar nada |
| **D-19** | **09-23** | **OpenCV completo en la imagen** | `zbar` (mucho más liviano) | Requisito del proyecto para reconocimiento futuro. Costo asumido: ~4 h de compilación |
| **D-20** | **09-24** | **Migrar de WSL2 a Ubuntu nativo** | Seguir en WSL2 con reenvío de puertos | WSL2 no expone V4L2 ni recibe UDP entrante. El receptor debe recibir |
| **D-21** | **09-24** | **Compilar desde cero en vez de migrar la caché** | Copiar 42 GiB de sstate por disco externo | Dos reinicios y transferencia manual contra compilación desatendida. El tiempo pasivo es más barato que el activo |
| **D-22** | **09-28** | **`v4l2jpegdec` en lugar de `jpegdec`** | Decodificador por software | `jpegdec` falla continuamente con los cuadros MJPEG de la cámara USB en la Pi (ver P-24) |
| **D-23** | **09-28** | **Resolución 640×480 en el destino** | Mantener 1280×720 | A 720p la cámara pierde cuadros en el bus USB |
| **D-24** | **09-28** | **Alcance: QR y no reconocimiento facial** | `face_recognition`, modelos DNN | `cv2.QRCodeDetector` ya está en la imagen y no requiere entrenamiento ni datos previos |
| **D-25** | **09-28** | **El QR llevará solo un identificador opaco; nombre y rol van impresos como texto en la imagen** | Codificar los datos personales dentro del QR | Un QR fotografiado no revela nada; la baja invalida la credencial aunque la imagen siga circulando |

---

## Registro de tiempos de compilación

| Fecha | Objetivo | Inicio | Fin | Duración | Notas |
|---|---|---|---|---|---|
| 09-10 | `core-image-base` (WSL2) | 11:09 | 23:17 | ~6 h | 5819 tareas. Sstate previo aportó 5%: era de `qemux86-64` |
| 09-23 | `acceso-control` (WSL2) | ___ | 15:06 | ~3.5 h | `RDEPENDS = packagegroup-acceso` arrastra GStreamer, Python y PyGObject completos |
| 09-23 | `opencv` (WSL2) | ~15:33 | 19:36 | ~4 h | 3345 tareas; `do_compile` sola tomó la mayor parte |
| **09-24/25** | **`acceso-image` (Ubuntu nativo, sin caché)** | ___ | **12:31** | **~10 h** | **7493 tareas, 0 % de sstate.** Imagen final: **149 MiB** comprimidos, 2246 paquetes |

---

## Registro de problemas y soluciones

| # | Fecha | Síntoma | Causa raíz | Solución | Tiempo |
|---|---|---|---|---|---|
| P-01 | 09-10 | `bitbake -e` sin salida, código 127 | Terminal nueva sin `oe-init-build-env` | Re-ejecutar el `source` | ~10 min |
| P-02 | 09-10 | Fallo de parseo de `local.conf` | Comilla sin abrir y typo `sysyemd` | `sed` + verificación con `bitbake -e` | ~15 min |
| P-03 | 09-10 | `Nothing RPROVIDES 'linux-firmware-rpidistro-bcm43456'` | Licencia restringida bloqueada por defecto | `LICENSE_FLAGS_ACCEPTED` | ~5 min |
| P-04 | 09-10 | Sstate compartido sin reutilización | `BB_HASHSERVE_DB_DIR` dentro del build | Apuntarlo a `${SSTATE_DIR}` | Detectado con `--dry-run` |
| P-05 | 09-10 | Windows congelado; `pgrep -c bitbake` = 0 | Falso negativo: BitBake corre como `python3` | `pgrep -af`, `uptime`, fecha de los `log.do_*` | ~15 min |
| P-06 | 09-10 | `Nothing RPROVIDES 'gstremaer1.0-tools'` | Typo en `RDEPENDS` | `sed` | ~2 min |
| P-07 | 09-10 | Mismo error tras corregir el typo | `gstreamer1.0-tools` **no existe** en 1.28.x | Eliminar la línea | ~10 min |
| P-08 | 09-19 | `x264enc` producía perfil `high-4:4:4` | El `capsfilter` no fijaba el formato de píxel | Añadir `format=I420` | ~20 min |
| P-09 | 09-19 | `fpsdisplaysink` no imprimía nada | En 1.24 dejó de escribir a stdout | Medir tiempo total en vez de contar cuadros | ~30 min |
| P-10 | 09-19 | Un `PERMITIR` tardío era aceptado tras el vencimiento | `esperar()` devolvía VENCIDO pero no cerraba la solicitud | Fijar el resultado y marcar el `Event` bajo lock | **Error crítico** |
| P-11 | 09-19 | Clip de 10 s salía corto | El búfer se dimensionaba solo con `segundos_antes` | Dimensionar con `antes + despues` | ~10 min |
| P-12 | 09-19 | `mp4mux`: "Buffer has no PTS" | Flujo elemental sin marcas de tiempo | `ffmpeg -r 30 -i ... -c copy` | ~25 min |
| P-13 | 09-19 | El clip empezaba en `00 00 00 02` | `h264parse` entregaba formato `avc` | Diagnosticado con `xxd`. Ver P-14 | ~15 min |
| P-14 | 09-19 | `not-negotiated` en bucle al añadir `capsfilter` | Un `tee` impone las mismas caps a TODAS sus ramas | Segundo `h264parse` en la rama del `appsink` | ~20 min |
| P-15 | 09-19 | Push rechazado: "fetch first" | La rama remota tenía commits hechos desde la web | `git pull --rebase origin Daniel` | ~10 min |
| **P-16** | **09-23** | **Los módulos Python quedaron en `/acceso/`, en la raíz del sistema de archivos** | **`${PYTHON_SITEPACKAGES_DIR}` se expandió VACÍA**: la receta no heredaba `python3-dir`. BitBake no advierte de variables indefinidas y `/acceso` es una ruta válida; el QA tampoco lo detectó porque `FILES` se expandió igual | `inherit systemd python3-dir` | **Error silencioso** |
| **P-17** | **09-23** | **`Nothing RPROVIDES 'python3-libgpiod'`** | `PACKAGES` de `libgpiod` no incluye enlaces de Python en esta versión | Se retira del packagegroup; queda `libgpiod-tools` | ~15 min |
| **P-18** | **09-23** | **`Nothing RPROVIDES 'ffmpeg'`** | Licencia `commercial` bloqueada | Se retira: `ffmpeg` se usa en la PC, no en la Pi. Error de alcance | ~5 min |
| **P-19** | **09-23** | **Segunda terminal: "No reply from server" en bucle** | **BitBake usa un único servidor por directorio de build** | No es error: es exclusión mutua. Para consultar metadatos mientras compila, leer las recetas con `grep` | ~5 min |
| **P-20** | **09-23** | **El build arrastró `mesa` y `llvm-native`, horas de compilación** | Cadena `plugins-base → opengl (activado por Poky) → mesa → llvm`. **La aplicación no usa OpenGL** | Detectado, no corregido: cambiar `DISTRO_FEATURES` invalida firmas. Pendiente: `DISTRO_FEATURES:remove = "opengl wayland x11"` | Hallazgo |
| **P-21** | **09-24** | **`liblz4-tool` no existe en Ubuntu 26.04** | Paquete de transición retirado | Sustituir por `lz4` | ~2 min |
| **P-22** | **09-24** | **`poky` no tiene rama `wrynose` en ningún espejo público** | El proyecto no la publica; el espejo de GitHub llega a `walnascar` | Clonar por separado: `openembedded-core` (`wrynose`), `bitbake` (**rama `2.18`**, otro esquema de nombres) y `meta-yocto` (`wrynose`) | ~40 min |
| **P-23** | **09-24** | **`User namespaces are not usable by BitBake, possibly due to AppArmor`** | Ubuntu 24.04+ restringe los espacios de nombres sin privilegios | Perfil en `/etc/apparmor.d/bitbake` con `flags=(unconfined)` y `userns,` | ~15 min |
| **P-24** | **09-24** | **`debug-tweaks is not a valid image feature`** | Retirada en Wrynose, dividida en features granulares | `allow-empty-password allow-root-login empty-root-password` | ~5 min |
| **P-25** | **09-28** | **La Pi arranca pero no se conecta al WiFi** | **El servicio busca su configuración en `/etc/wpa_supplicant/`, no en `/etc/`.** Arrancaba, no encontraba el archivo y moría al instante | Mover el `.conf` al subdirectorio correcto. Diagnosticado leyendo el `ExecStart` de la unidad | **~4 h** |
| **P-26** | **09-28** | **`v4l2h264enc` falla desde `gst-launch`: "Failed to process frame"** | `bcm2835_codec_start_streaming: Failed enabling i/p port, ret -3` (firmware VideoCore). CMA descartada: 450 MB libres de 524 | **Sin resolver desde `gst-launch`, pero funciona dentro de la aplicación** con los `extra-controls` configurados | Hallazgo |
| **P-27** | **09-28** | **`jpegdec` falla continuamente: "Failed to decode JPEG image"** | El decodificador por software no procesa los cuadros MJPEG de esta cámara USB | `v4l2jpegdec ! v4l2convert` (decodificador por hardware) | ~20 min |
| **P-28** | **09-28** | **Evidencia y bitácora no aparecían en `/var/lib/acceso/`** | Las rutas en `acceso.conf` eran **relativas** y systemd fija el cwd en `/`; los archivos quedaban en `/evidencia/` y `/accesos.log` | Rutas absolutas en la configuración | ~15 min |
| **P-29** | **09-28** | **IP de la Pi y de la laptop cambian cada pocos minutos** | Arriendos DHCP cortos en la red institucional (`valid_lft` ~28 min) | Identificar la Pi por MAC (`d8:3a:dd`, Raspberry Pi Trading) con `arp-scan` | Recurrente |
| **P-30** | **09-28** | **Sesión SSH bloqueada dentro de `vi`** | BusyBox `vi` en modo inserción; `:q!` se escribía en el archivo | `Esc` + `:q!`, o secuencia de escape SSH `Enter` `~` `.`. **Regla adoptada: editar en el destino solo con `sed`** | ~15 min |

---

## Entradas diarias

### 2026-09-10 · ___ h — Plataforma: árbol de capas e imagen base

_(entrada previa sin cambios — ver historial del repositorio)_

---

### 2026-09-19 · ___ h — Aplicación: pipeline, búfer circular y decisión de acceso

_(entrada previa sin cambios — ver historial del repositorio)_

---

### 2026-09-23 · ___ h — Empaquetado, imagen y OpenCV

**Objetivo de la sesión**

Convertir la aplicación validada en un paquete que la imagen instale y
systemd arranque solo, desglosar las dependencias a nivel de subpaquete y
compilar OpenCV.

**Actividades**

1. Derivación de la lista real de plugins: cada elemento de la tubería mapeado
   a su biblioteca con `gst-inspect-1.0 | grep Filename`, y de ahí al subpaquete.
2. Reescritura de `packagegroup-acceso.bb` con subpaquetes individuales y
   separación del bloque de diagnóstico.
3. Redacción de `acceso-control_1.0.bb`: instalación manual, `CONFFILES`,
   `RDEPENDS` al packagegroup.
4. Unidad systemd con `Restart=on-failure`, `RestartSec=5`, `TimeoutStopSec=20`,
   `StateDirectory` y `RuntimeDirectory`.
5. Script `sincronizar-receta.sh` para mantener al día la copia que la receta
   consume vía `file://`.
6. Compilación de `acceso-control`, diagnóstico y corrección de P-16.
7. Merge de `origin/main` con los cambios del compañero.
8. Redacción de `acceso-image.bb` con SSH (dropbear).
9. Configuración y compilación de OpenCV 4.13.0.

**Resultados**

Empaquetado verificado tras corregir P-16:

```
/usr/bin/acceso-control
/etc/acceso/acceso.conf
/usr/lib/systemd/system/acceso-control.service
/usr/lib/python3.14/site-packages/acceso/{8 módulos}
```

`log.do_package_qa` sin advertencias. OpenCV compilado, con
`libopencv-objdetect413` (donde reside `QRCodeDetector`) y
`cv2.cpython-314-aarch64-linux-gnu.so`.

**Aprendizajes**

- **Una variable de clase no heredada se expande vacía sin producir error.**
  El paquete resultante era internamente coherente y completamente inútil.
  Solo se detecta inspeccionando el directorio `image/` antes de construir.
- **Las dependencias se derivan, no se adivinan.** El mapeo reveló que
  `splitmuxsink` vive en `multifile` y no en `isomp4`.
- **Una imagen "mínima" no lo es por omisión.** Poky activa `opengl`, y esa
  sola feature arrastró Mesa y LLVM para un dispositivo sin monitor.

---

### 2026-09-24/25 · ___ h — Migración a Linux nativo y compilación de la imagen

**Objetivo de la sesión**

Migrar el entorno de desarrollo a Ubuntu nativo y reconstruir el árbol de
capas desde cero para compilar la imagen completa del proyecto.

**Actividades**

1. Instalación de dependencias de Yocto, GStreamer, PyGObject y OpenCV en
   Ubuntu 26.04 nativo.
2. Clonación del árbol de capas desde cero (ver P-22).
3. Resolución de la restricción de AppArmor (P-23).
4. Reconstrucción de `local.conf`, incluyendo `RPI_EXTRA_CONFIG` con
   `gpio=27=op,dl` y `gpio=22=op,dl` para el estado seguro de los indicadores.
5. Corrección de `debug-tweaks` (P-24).
6. Compilación completa de `acceso-image`: 7493 tareas sin caché.
7. Verificación del manifiesto y grabado de la microSD.

**Resultados**

- Imagen de **149 MiB** comprimidos, 2246 paquetes.
- Manifiesto verificado: `acceso-control`, `python3-opencv`,
  `gstreamer1.0-python`, `python3-pygobject`, `dropbear`, `libgpiod-tools`.
- `config.txt` de la partición de arranque confirmado con `enable_uart=1`,
  `gpio=27=op,dl` y `gpio=22=op,dl`.
- Cámara USB verificada en el host: MJPEG 1280×720@30 en `/dev/video2`.

**Aprendizajes**

- **La documentación de Yocto asume un `poky` monolítico que no existe para
  esta serie.** Hubo que reconstruir la estructura clonando tres repositorios
  por separado, con bitbake usando un esquema de nombres de rama distinto.
- **`git://` está bloqueado en muchas redes.** Todos los clones deben usar
  HTTPS; es un obstáculo que aparece de inmediato en una máquina limpia.
- Los tres hallazgos de esta sesión (P-21 a P-24) son exactamente el tipo de
  detalle que hace que un tutorial funcione o no en otra máquina.

---

### 2026-09-28 · ___ h — Verificación completa sobre la Raspberry Pi 4

**Objetivo de la sesión**

Arrancar la imagen en hardware real y verificar el sistema completo:
conectividad, plataforma, cámara, codificación, transmisión y casos de uso.

**Actividades**

1. Grabado de la microSD con `bmaptool` (65 s con `.bmap`).
2. Primer arranque: la imagen llega al prompt de login.
3. Diagnóstico y resolución de la conectividad WiFi (P-25), ~4 h.
4. Inventario de plataforma en el destino.
5. Diagnóstico del codificador por hardware (P-26).
6. Transmisión MJPEG directa como prueba de concepto de CU-1.
7. Corrección del decodificador (P-27) y de las rutas (P-28).
8. Ejecución de los tres casos de uso de decisión de acceso.
9. Extracción de evidencia a la laptop.

**Comandos relevantes**

```bash
# Grabado
sudo bmaptool copy --bmap acceso-image-...wic.bmap acceso-image-...wic.bz2 /dev/sdX

# Localizar la Pi por MAC de fabricante
sudo arp-scan --localnet --retry=5 | grep -i "d8:3a:dd"

# Verificación de plataforma en el destino
python3 -c "import gi, cv2; gi.require_version('Gst','1.0'); from gi.repository import Gst; Gst.init(None); print(Gst.version_string(), cv2.__version__)"
v4l2-ctl --list-devices
gpioget -c gpiochip0 27 22

# Transmisión (emisor en la Pi)
gst-launch-1.0 v4l2src device=/dev/video0 ! image/jpeg,width=1280,height=720,framerate=30/1 \
  ! rtpjpegpay ! udpsink host=<IP_LAPTOP> port=5000

# Receptor (laptop)
gst-launch-1.0 -v udpsrc port=5000 caps="application/x-rtp,media=(string)video,clock-rate=(int)90000,encoding-name=(string)JPEG,payload=(int)26" \
  ! rtpjpegdepay ! jpegdec ! videoconvert ! autovideosink sync=false

# Casos de uso
echo "SOLICITUD ID-100" > /tmp/acceso-eventos
echo "PERMITIR"         > /tmp/acceso-eventos
cat /var/lib/acceso/accesos.log
```

**Resultados verificados en el destino**

| Verificación | Resultado |
|---|---|
| Arranque de la imagen propia | Llega al login, servicio habilitado |
| WiFi + SSH | Funcional tras P-25 |
| `Gst.version_string()` | **GStreamer 1.28.5** |
| `cv2.__version__` | **4.13.0** |
| Elementos de GStreamer | 9 de 9 presentes (`v4l2src`, `v4l2h264enc`, `v4l2convert`, `h264parse`, `splitmuxsink`, `rtph264pay`, `udpsink`, `appsink`, `jpegdec`) |
| Codificador por hardware | `/dev/video11` registrado (`bcm2835-codec: Loaded V4L2 encode`) |
| Cámara USB en el destino | `/dev/video0`, MJPEG 1280×720@30 |
| GPIO al arranque | `"27"=inactive "22"=inactive` — **estado seguro confirmado** |
| Reinicio automático | Verificado (`restart counter is at 26` durante el diagnóstico) |
| Transmisión en vivo a la laptop | **Funcional** |
| Grabación MP4 | Segmentos válidos: `Duration 00:00:32.50`, h264 Baseline, 1280×720 |
| Carga del sistema en operación | **93 % de CPU libre, load average 0.01, 7.5 GB de RAM libre** |

Bitácora de accesos con los tres resultados, generada sobre la Raspberry Pi:

```
ID-100  permitido                  5929.9 ms
ID-101  denegado                   5150.8 ms
ID-102  denegado_por_vencimiento  30000.9 ms
```

**Aprendizajes**

- **El diagnóstico a ciegas es carísimo.** Sin teclado, sin cable de red y sin
  adaptador UART, cada hipótesis sobre el WiFi costaba diez minutos: sacar la
  tarjeta, montarla, editar, insertar, arrancar, observar. La causa (P-25)
  resultó ser una sola línea del `ExecStart` de la unidad de systemd, y se
  encontró leyendo la unidad en vez de probando configuraciones.
- **La ruta que un servicio espera no siempre es la documentada.** Conviene
  leer el `ExecStart` antes de escribir cualquier archivo de configuración.
- **Los resultados en el destino no se deducen del host.** `jpegdec` funciona
  en la laptop y falla en la Pi con la misma cámara; `v4l2h264enc` falla desde
  `gst-launch` y funciona dentro de la aplicación. Ambos hallazgos solo
  aparecen sobre hardware.
- **Las rutas relativas y systemd no se llevan bien.** `StateDirectory` no
  cambia el directorio de trabajo, que queda en `/`. Los archivos aparecieron
  en la raíz del sistema de archivos, no donde se esperaba.
- **La carga del sistema desmintió una preocupación.** Se asumía que la Pi
  estaría al límite; está al 7 % de uso. Los cuadros perdidos son del bus USB,
  no falta de procesador. Hay margen amplio para agregar procesamiento.

**Limitaciones declaradas**

| Limitación | Estado |
|---|---|
| Tasa efectiva de captura: **4.28 fps** contra 30 solicitados | Pérdida de cuadros en el bus USB (`lost frames detected`). Limitación de la cámara disponible, no del diseño |
| `v4l2h264enc` falla desde `gst-launch` | Funciona dentro de la aplicación; causa en el firmware VideoCore sin resolver |
| Clip de pre-evento: campo `clip: null` | El búfer circular no escribió el clip en el destino. Pendiente de diagnóstico |
| Hardware rotativo | Las Raspberry Pi y microSD cambian entre sesiones; no hay equipo fijo |

**Pendientes**

- [ ] Diagnosticar por qué el clip de pre-evento sale `null` en el destino
- [ ] Tutorial paso a paso de síntesis e instalación
- [ ] Reconstrucción limpia sin `sstate-cache`
- [ ] Quitar `opengl wayland x11` de `DISTRO_FEATURES`
- [ ] Llevar al repositorio los cambios hechos en vivo sobre `acceso.conf`
- [ ] Corrida de estabilidad de 4 h

**Coordinación con el compañero**

- Entregada la lista de elementos GStreamer usados, base del packagegroup.
- Informado: OpenCV 4.13.0 disponible en la imagen, compilado **sin** soporte
  GStreamer; los cuadros llegan por el `appsink` y se convierten a NumPy.
- Acordado el alcance del reconocimiento: **QR, no facial** (D-24), con el
  vigilante como quien genera y revoca las credenciales.
- Retirados `app.zip` y `app.7z` del repositorio: duplicaban código versionado.

---

### AAAA-MM-DD · ___ h

**Objetivo de la sesión**

**Actividades**

1.

**Comandos relevantes**

```bash

```

**Resultados**

**Problemas encontrados**

| Síntoma | Hipótesis | Qué se probó | Resultado |
|---|---|---|---|
|  |  |  |  |

**Aprendizajes**

**Pendientes**

- [ ]

**Coordinación con el compañero**

---

## Resumen final

_(se completa al cierre del proyecto)_

- Horas totales dedicadas:
- Requerimientos verificados personalmente:
- Contribución principal al equipo:
- Qué haría distinto en un proyecto siguiente:
