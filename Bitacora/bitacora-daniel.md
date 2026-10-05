# Bitácora individual de trabajo

**Estudiante:** Daniel Chavarría García
**Rol en el equipo:** B — Plataforma (Yocto, BSP, imagen) · asumió temporalmente el Rol A
**Proyecto 1 — Sistema de control de acceso con Yocto Project y GStreamer**
**Taller de Sistemas Embebidos · TEC · II Semestre 2026**
**Prof. Dr. Ing. Johan Carvajal Godínez**

---

## Entorno de trabajo

| Elemento | Valor |
|---|---|
| Host | Ubuntu 26.04.1 LTS · kernel 7.0.0-34-generic · 4 núcleos |
| RAM / swap | 8 GiB / 4 GiB |
| Yocto | Poky 6.0.3 / oe-core serie **wrynose** |
| BitBake | 2.18 |
| Máquina destino | `raspberrypi4-64` (RPi 4B Rev 1.5, `TUNE_FEATURES = aarch64 crc cortexa72 nocrypto`) |
| GStreamer en la imagen | 1.28.5 |
| Python en la imagen | 3.14.7 |
| OpenCV en la imagen | 4.13.0 (`python3-opencv`) |
| Directorio de compilación | `~/proyecto-acceso/build` |
| Aplicación (Rol A) | `~/proyecto-acceso/app` |
| Capa propia | `~/proyecto-acceso/meta-acceso` (enlazada desde `layers/`) |
| Repositorio | `github.com/YzakVander/Proyecto1_embebidos`, rama `Daniel` |
| Hardware | RPi4 y microSD del laboratorio (acceso intermitente); cámara **USB** (DV20 UVC) autorizada por el profesor |

---

## Registro de decisiones de diseño

| # | Fecha | Decisión | Alternativas consideradas | Justificación |
|---|---|---|---|---|
| D-01 | 09-10 | `DISTRO = "poky"` | Build distro-less | meta-raspberrypi declara Poky como su foco de pruebas; base conocida de `DISTRO_FEATURES` |
| D-02 | 09-10 | `INIT_MANAGER = "systemd"` | sysvinit | RF-10 y RF-11 se resuelven con una unidad; el cierre ordenado del MP4 requiere `TimeoutStopSec` |
| D-03 | 09-10 | Capas por enlace simbólico | Clonar árbol nuevo | Evita duplicar ~2 GiB; los builds quedan independientes |
| D-04 | 09-10 | Aceptar `synaptics-killswitch` | Excluir `packagegroup-base-extended` | `core-image-base` arrastra el firmware WiFi por diseño |
| D-05 | 09-10 | Cámara **USB (UVC)** con `v4l2src` | CSI con `libcamerasrc` | Autorizado por el profesor; elimina el riesgo técnico más alto |
| D-06 | 09-10 | Conjuntos completos de plugins en la 1.ª iteración | Subpaquetes desde el inicio | Primero funcionar, después afinar |
| D-07 | 09-10 | Compilar en casa, verificar en laboratorio | QEMU para todo | Acceso intermitente a la RPi4 |
| D-08 | 09-19 | `appsink` con búfer circular de pre-evento | `split-now`; cuadro único | El clip necesita contexto ANTES del evento: una cámara de vigilancia real hace pre-roll |
| D-09 | 09-19 | Guardar cuadros H.264 comprimidos, no crudos | Cuadros I420 en RAM | 10 s comprimidos = 235 KiB medidos, contra ~415 MB crudos |
| D-10 | 09-19 | Ventana del clip: 5 s antes + 5 s después | 3+2 | Más contexto para auditar; con cuadros comprimidos el costo en RAM es irrelevante |
| D-11 | 09-19 | E3: reconectar con alerta, no morir | Morir y que systemd reinicie | El acta acepta ambas pero exige decidir. Reintentos indefinidos cada 5 s |
| D-12 | 09-19 | H2: plazo de 30 s, vencimiento DEFINITIVO | 5 s, 10 s | 30 s da margen a una persona real (latencias medidas: 6.8 s y 15.9 s) |
| D-13 | 09-19 | H6: archivo JSONL con `fsync` | journald | Un archivo se inspecciona con `cat`; `fsync` lo protege de corte de energía |
| D-14 | 09-19 | B4/B5 se CUMPLEN, no se declaran N/A | Declararlos no aplicables | Único N/A legítimo: **H4** (no hay cerradura física; el actuador es un buzzer indicador) |
| D-15 | 09-23 | Desglosar `packagegroup-acceso` a subpaquetes derivados de la tubería real | Mantener los conjuntos `-good`/`-bad` | Cumple G1. La lista **no se adivinó**: se obtuvo mapeando cada elemento a su biblioteca con `gst-inspect-1.0 \| grep Filename` |
| D-16 | 09-23 | `videotestsrc` y las herramientas van en `-diagnostico` | Un solo paquete con todo | La imagen de producción no debe llevar la fuente de prueba usada en desarrollo (G2) |
| D-17 | 09-23 | SSH (dropbear) en la imagen | Imagen sin acceso remoto | Permite iterar el código Python con `scp` + `systemctl restart` sin regenerar la imagen |
| D-18 | 09-23 | Instalación manual en `do_install` en vez de `inherit setuptools3` | Empaquetado PEP 517 | Módulos sin dependencias de compilación; `setuptools3` agregaría paquetes al build sin aportar nada |
| D-19 | 09-23 | OpenCV para la lectura de QR | `zbar` (mucho más liviano) | Requisito del proyecto. Se asume el costo: ~4 h de compilación |
| D-20 | 09-23 | El QR separa identificación de autorización | Sustituir al vigilante por el QR | El lector **identifica**; el vigilante **autoriza**. Si el QR no resuelve, escala al vigilante con el plazo de H2 |
| D-21 | 09-23 | El reconocimiento de QR corre en la RPi4, no en el puesto de vigilancia | Procesar en la máquina receptora | Un control de acceso que depende del puesto remoto para abrir la puerta es frágil. La Pi decide sola e informa |
| **D-22** | **09-2_** | **Buzzer pasivo en GPIO 18 por PWM de hardware** | LEDs indicadores; conmutar el pin desde Python | El buzzer no oscila solo: necesita onda cuadrada. Conmutar a 2.5 kHz desde Python daría tono irregular y consumiría CPU que necesitan GStreamer y el codificador |
| **D-23** | **09-2_** | **Destino de transmisión automático: la Pi redirige el RTP a quien se conecte al canal TCP** | IP fija en `acceso.conf` | El DHCP del laboratorio rota las direcciones cada ~30 min. Con IP fija, cada sesión empezaba reconfigurando el archivo en la placa |
| **D-24** | **09-2_** | **La revocación de credenciales es permanente, sin reactivación** | Permitir reactivar una credencial dada de baja | Una credencial revocada puede estar circulando impresa o fotografiada. Reactivar el mismo identificador devolvería acceso a copias que se creían anuladas. Para readmitir a una persona se emite un identificador nuevo |
| **D-25** | **10-02** | **Dos recetas de imagen: `acceso-image` (entrega) y `acceso-image-dev`** | Comentar las líneas de desarrollo antes de entregar | Comentar y descomentar es frágil: es lo que se olvida a última hora. La de desarrollo hereda de la de entrega y agrega las concesiones (G2) |
| **D-26** | **10-02** | **`RDEPENDS` de la aplicación a nivel de subpaquete, no al metapaquete** | `RDEPENDS = "packagegroup-acceso"` | Si la receta se instala en otra imagen sin ese packagegroup, el paquete queda sin un solo plugin y el servicio muere en el arranque. La aplicación declara lo que necesita (G1) |
| **D-27** | **10-02** | **Ante la imposibilidad de usar `ffprobe` y `top -H` en la placa, se usa método equivalente y se documenta** | Agregar `ffmpeg` y `procps` a la imagen | El acta busca verificar que el MP4 tenga índice y medir CPU por hilo durante 60 s; ambas cosas se logran con lo que la imagen trae (lectura de cajas MP4, `/proc/<pid>/stat`). Agregar las herramientas contradiría el principio de imagen mínima |
| **D-28** | **10-04** | **Sello de fecha y hora en el video con `clockoverlay`, antes del codificador** | Marca de agua en la aplicación; sin sello | Insertado antes del codificador queda en los tres destinos (grabación, clips y transmisión). Va después del `tee` de la rama de codificación, de modo que **no afecta a la rama del lector de QR** |

---

## Registro de tiempos de compilación

| Fecha | Objetivo | Duración | Notas |
|---|---|---|---|
| 09-10 | `core-image-base` | ~6 h | 5819 tareas. Sstate previo solo aportó 5%: era de `qemux86-64` |
| 09-23 | `acceso-control` | ~3.5 h | Mucho más de lo esperado para una receta que solo copia archivos: `RDEPENDS = packagegroup-acceso` arrastra GStreamer, Python y PyGObject completos |
| 09-23 | `opencv` (PACKAGECONFIG mínimo) | ~4 h | 3345 tareas. `do_compile` sola tomó la mayor parte |
| 10-02 | `acceso-image` con x264 | ~2 h | 7567 tareas, 7413 desde sstate |
| 10-04 | `acceso-image` + `acceso-image-dev` | ~15 min | 7644 tareas, 7601 desde sstate. Con sstate caliente la reconstrucción es barata |
| 10-04 | Ídem + análisis de CVE | — | La descarga del índice de vulnerabilidades domina el tiempo |

> Con `BB_NUMBER_THREADS = "2"` y `PARALLEL_MAKE = "-j 2"`, valores elegidos
> por los 8 GiB de RAM: subirlos arriesga que el OOM killer mate el build.

---

## Registro de problemas y soluciones

| # | Fecha | Síntoma | Causa raíz | Solución | Tiempo |
|---|---|---|---|---|---|
| P-01 | 09-10 | `bitbake -e` sin salida, código 127 | Terminal nueva sin `oe-init-build-env` | Re-ejecutar el `source` | ~10 min |
| P-02 | 09-10 | Fallo de parseo de `local.conf` | Comilla sin abrir y typo `sysyemd` | `sed` + verificación con `bitbake -e` | ~15 min |
| P-03 | 09-10 | `Nothing RPROVIDES 'linux-firmware-rpidistro-bcm43456'` | Licencia restringida bloqueada por defecto | `LICENSE_FLAGS_ACCEPTED` | ~5 min |
| P-04 | 09-10 | Sstate compartido sin reutilización | `BB_HASHSERVE_DB_DIR` dentro del build | Apuntarlo a `${SSTATE_DIR}` | Detectado con `--dry-run` |
| P-05 | 09-10 | `pgrep -c bitbake` = 0 con el build corriendo | Falso negativo: BitBake corre como `python3` | `pgrep -af`, fecha de los `log.do_*` | ~15 min |
| P-06 | 09-10 | `Nothing RPROVIDES 'gstremaer1.0-tools'` | Typo en `RDEPENDS` | `sed` | ~2 min |
| P-07 | 09-10 | Mismo error tras corregir el typo | La receta `gstreamer1.0-tools` **no existe** en esta versión | Eliminar la línea | ~10 min |
| P-08 | 09-19 | `x264enc` producía perfil `high-4:4:4` | El `capsfilter` no fijaba el formato de píxel | Añadir `format=I420` | ~20 min |
| P-09 | 09-19 | `fpsdisplaysink` no imprimía nada | En 1.24 dejó de escribir a stdout | Medir tiempo total en vez de contar cuadros | ~30 min |
| P-10 | 09-19 | Un `PERMITIR` tardío era aceptado tras el vencimiento | `esperar()` devolvía VENCIDO pero no cerraba la solicitud | Fijar el resultado y marcar el `Event` bajo lock | **Error crítico** |
| P-11 | 09-19 | Clip de 10 s salía corto | El búfer se dimensionaba solo con `segundos_antes` | Dimensionar con `antes + despues` | ~10 min |
| P-12 | 09-19 | `mp4mux`: "Buffer has no PTS" | Flujo elemental sin marcas de tiempo | `ffmpeg -r 30 -i ... -c copy` | ~25 min |
| P-13 | 09-19 | El clip empezaba en `00 00 00 02`, no era Annex B | `h264parse` entregaba formato `avc` | Diagnosticado con `xxd`. Ver P-14 | ~15 min |
| P-14 | 09-19 | `not-negotiated` en bucle al añadir `capsfilter` | Un `tee` impone las mismas caps a TODAS sus ramas | Segundo `h264parse` en la rama del `appsink` | ~20 min |
| P-15 | 09-19 | Push rechazado: "fetch first" | La rama remota tenía commits hechos desde la web | `git pull --rebase origin Daniel` | ~10 min |
| P-16 | 09-23 | Los módulos Python quedaron en `/acceso/`, en la raíz del sistema de archivos | `${PYTHON_SITEPACKAGES_DIR}` se expandió VACÍA: la receta no heredaba `python3-dir`. BitBake no advierte de variables indefinidas y `/acceso` es ruta válida | `inherit systemd python3-dir` | **Error silencioso** |
| P-17 | 09-23 | `Nothing RPROVIDES 'python3-libgpiod'` | El paquete no existe con ese nombre en esta versión | Se retira del packagegroup; queda `libgpiod-tools` | ~15 min |
| P-18 | 09-23 | `Nothing RPROVIDES 'ffmpeg'` | Licencia `commercial`, bloqueada por defecto | Se retira: `ffmpeg` se usa en la PC, no en la Raspberry. Error de alcance | ~5 min |
| P-19 | 09-23 | Segunda terminal: "No reply from server" en bucle | BitBake usa un único servidor por directorio de build | No es error: es exclusión mutua. Consultar metadatos con `grep` mientras compila | ~5 min |
| P-20 | 09-23 | El build arrastró `mesa` y `llvm-native` | Cadena `plugins-base → opengl (activado por Poky) → mesa → llvm`. La aplicación no usa OpenGL | Detectado, no corregido: cambiarlo invalida firmas. Pendiente `DISTRO_FEATURES:remove` | Hallazgo |
| P-21 | 09-23 | `PACKAGECONFIG:pn-opencv = "python3"` no redujo los módulos | Se generaron igual `gapi`, `tracking`, `xfeatures2d` y el resto de contrib | Sin resolver | Pendiente |
| **P-22** | **10-01** | **Sin acceso a la placa: credenciales desconocidas** | Imagen propia sin documentar la contraseña | Montar la microSD en la laptop e inspeccionar `/etc/shadow`: root tenía el campo de contraseña **vacío**, que funciona en consola pero **no por SSH** (dropbear y OpenSSH rechazan contraseñas vacías por diseño) | ~1 h |
| **P-23** | **10-01** | **`/etc/shadow` editado a mano quedó malformado** | Dos puntos mal colocados al insertar el hash de `openssl passwd -6` | Comparar el formato campo por campo contra una línea sana; verificar el conteo con `awk -F:` antes de arrancar | ~20 min |
| **P-24** | **10-02** | **`gst-launch` externo falla con `Failed enabling i/p port, ret -3` y el kernel emite un WARNING en `vb2_start_streaming`** | Los cinco nodos `/dev/video10,11,12,18,31` son el **mismo bloque** `bcm2835-codec`. La aplicación usa cinco contextos simultáneos (2 `v4l2jpegdec` + 2 `v4l2convert` + 1 `v4l2h264enc`) y no queda margen para un proceso externo | Descartadas por medición: CMA (512 MiB reservados, 507 libres), `gpu_mem` subido a 256 (falla igual a 640×480) y los tres modos de `io-mode`. Para medir a mano: detener el servicio y esperar ~10 s | **~2 h** |
| **P-25** | **10-02** | **El EOS no llegaba al bus: el último MP4 quedaba con `mdat` de 0 bytes y sin `moov`** | Para llegar a `splitmuxsink` el EOS debe atravesar `v4l2jpegdec`, `v4l2convert` y `v4l2h264enc`, que al recibirlo vacían el bloque de hardware. En la RPi 4 ese vaciado no termina: el plazo de 10 s se agotaba siempre completo | Diagnóstico propio con `GST_DEBUG` y `kill -TERM` directo (descartando systemd). Corrección del Rol A: inyectar el EOS en la queue de grabación y esperar `splitmuxsink-fragment-closed`. **Cierre de 10 s → 10 ms** | **Defecto crítico** |
| **P-26** | **10-02** | **Tras un `kill -9`, el servicio reinicia y reporta PLAYING pero NO GRABA** | El bloque `bcm2835-codec` queda en estado inservible. Segmentos de 595 B en vez de 17.4 MB/min, con el mismo `ret -3` en `dmesg` como único síntoma | **Solo un reboot lo recupera**, verificado. systemd cumple su parte (E6) pero la recuperación no es funcional. Documentado como limitación | **Hallazgo** |
| **P-27** | **10-02** | **La receta de Yocto tenía código viejo: `retencion.py` ausente y cinco módulos desactualizados** | La receta consume una **copia** de `app/` vía `file://`, y `sincronizar-receta.sh` no se había corrido antes de compilar. Nada lo advierte: el build pasa sin error | Encontrado por comparación sistemática (`diff -rq`) entre `app/acceso/` y la copia de la receta. Explica por qué se venían copiando módulos por `scp` en vez de confiar en la imagen | **Error silencioso** |
| **P-28** | **10-04** | **La medición de F5 daba 645 MB/h y los segmentos pesaban 17.4 MB/min (~1050 MB/h)** | Se midió el **crecimiento neto** de la carpeta, mientras la retención borraba en paralelo | Tres cifras distintas y válidas: neto 645 MB/h, escritura al dispositivo 710 MB/h (`/proc/diskstats`), bruta ~1050 MB/h. La retención efectiva se calcula con la bruta: **5.2 h**, no 8.5 h | ~20 min |
| **P-29** | **10-04** | **`G2-dos-imagenes.txt` reportaba imágenes de 58 bytes** | Se midió con `ls -lh` el **enlace simbólico**, no el archivo | `ls -lLh`. Tamaños reales: 159 MB (entrega) y 162 MB (desarrollo) | ~10 min |
| **P-30** | **10-04** | **`INHERIT += "cve-check"` y luego `"sbom-cve-check"` rompen el parseo de BitBake** | En wrynose la clase se renombró a `sbom-cve-check` **y** vive en `classes-recipe/`, que solo se hereda desde una receta, no desde `local.conf` | Se activa con un **fragmento de configuración**, mecanismo nuevo de Yocto 5.x: `OE_FRAGMENTS += "core/yocto/sbom-cve-check"` | ~40 min |

---

## Entradas diarias

### 2026-09-10 — Plataforma: árbol de capas e imagen base

_(entrada previa sin cambios — ver historial del repositorio)_

---

### 2026-09-19 — Aplicación: pipeline, búfer circular y decisión de acceso

_(entrada previa sin cambios — ver historial del repositorio)_

---

### 2026-09-23 — Plataforma: empaquetado, imagen y OpenCV

_(entrada previa sin cambios — ver historial del repositorio)_

---

### 2026-10-01 — Recuperación del acceso a la placa

**Objetivo.** Recuperar el acceso a una Raspberry Pi con imagen propia cuyas
credenciales no estaban documentadas, para poder seguir verificando.

**Qué se hizo.** Se montó la microSD en la laptop y se inspeccionó el sistema
de archivos, confirmando que corría Poky 6.0.3 y no Raspberry Pi OS. La
revisión de `/etc/shadow` mostró que root tenía el campo de contraseña vacío.

Ese hallazgo tiene un matiz que vale registrar: **una contraseña vacía permite
entrar por consola pero no por SSH**, porque tanto dropbear como OpenSSH
rechazan la autenticación vacía por diseño. Era por eso que la placa parecía
inaccesible aun teniendo una cuenta sin clave.

Se generó un hash con `openssl passwd -6` y se editó `/etc/shadow` directamente
sobre la tarjeta montada. El primer intento quedó malformado por dos puntos mal
colocados (P-23) y hubo que corregirlo comparando el formato campo por campo.

**Aprendizaje.** Una imagen sin credenciales documentadas es una imagen que
puede quedar inservible. El procedimiento de recuperación —montar la tarjeta y
editar `/etc/shadow`— funciona, pero cuesta una hora que no debería gastarse.
Este episodio motivó la decisión D-25: separar la imagen de entrega de la de
desarrollo y documentar explícitamente cómo se accede a cada una.

---

### 2026-10-02 — Verificación sistemática contra el acta (sesión larga)

**Objetivo.** Contrastar el estado real del proyecto contra los 44 ítems del
acta de validación, ejecutando en la placa todo lo que estuviera pendiente del
lado de plataforma.

**Punto de partida.** 11 ítems cumplidos, ninguno de los siete criterios de
aceptación cerrado. El diagnóstico fue que **casi toda la evidencia estaba
medida en x86_64 con `videotestsrc`**, no en la plataforma final. No había
certeza de que el sistema corriera de verdad en la Raspberry.

**Lo que se cerró**

| Ítem | Resultado |
|---|---|
| C1 | Codificador por hardware verificado: `/dev/video11`, sus 12 controles y los 14 formatos que acepta |
| G3 | Registro de plugins regenerado desde cero; los 13 elementos de la tubería dan OK; 41 plugins, 447 features |
| G5 | Commits exactos de las cinco capas, GStreamer 1.28.5, kernel 6.18.33, Poky 6.0.3 |
| E6 | `kill -9` → systemd reinicia, `NRestarts` sube. `stop` ordenado → queda inactivo |
| F5 | Caudal medido; margen holgado contra los topes de retención |
| E4 | Defecto encontrado, diagnosticado y verificado tras la corrección |
| RF-7 | Retención verificada con topes reducidos: diez ciclos de borrado, carpeta estabilizada bajo el tope |

**Los tres hallazgos de la sesión** están registrados como P-24, P-25 y P-26.
El de mayor valor fue el del EOS: se descartaron por medición las tres
hipótesis que apuntaban al elemento de GStreamer y se acotó la causa a la
cadena V4L2. El Rol A implementó la corrección y la verificación posterior
mostró el cierre pasando de 10 s agotados a **10 ms**, con `mdat` de 12 MB y
`moov` presente.

**Lo que no se pudo cerrar.** C2 quedó a medias: la ruta por hardware está
medida (4.2 % de CPU con el servicio completo), pero **no hay ningún
codificador H.264 por software en la imagen** —`x264enc`, `openh264enc`,
`avenc_h264` y `vp8enc` faltan todos—, de modo que no hay con qué comparar.
Eso dejó ver además que la contingencia prevista en el plan de trabajo
("cambiar a `x264enc`, una línea en `acceso.conf`") **no era ejecutable**.

**Aprendizajes**

- **Un síntoma puede tener una causa que no está donde apunta.** El `ret -3`
  parecía un driver roto; `v4l2-ctl` demostró que el hardware funcionaba. La
  diferencia estaba en cuántos contextos del bloque había abiertos.
- **Descartar hipótesis por medición vale tanto como confirmarlas.** CMA,
  `gpu_mem` y los tres modos de `io-mode` se descartaron con datos, no con
  argumentos. Ese registro es lo que permitió llegar a la causa real.
- **Un servicio "activo" no es un servicio que funciona.** Tras el `kill -9`,
  systemd reportaba `active (running)` y el log decía `tubería en PLAYING`
  mientras no se grababa nada. Vigilar el proceso no alcanza; hay que vigilar
  su producto.

---

### 2026-10-04 — Plataforma: G1, G2, sincronización y entregables

**Objetivo.** Cerrar los ítems de Yocto que no dependen de la placa y poner al
día la documentación.

**Qué se hizo**

1. **G1.** Reescritura del `RDEPENDS` de `acceso-control` a nivel de subpaquete
   (D-26). Se descubrió que `python3-numpy` no estaba declarado en ninguna parte
   pese a que `pipeline.py` lo importa, y que `python3-opencv` colgaba suelto del
   `IMAGE_INSTALL` en vez de declararlo quien lo usa.
2. **G2.** Separación en dos recetas de imagen (D-25). Verificado con los
   manifiestos: la de entrega lleva **0** paquetes de `plugins-ugly` y la de
   desarrollo **8**; 2250 contra 2266 paquetes; 159 MB contra 162 MB.
3. **P-27.** Comparación sistemática entre `app/acceso/` y la copia de la receta:
   `retencion.py` ausente y cinco módulos desactualizados. Corregido con
   `sincronizar-receta.sh` y documentado como paso obligatorio del build.
4. Agregado de `raspi-utils` al subpaquete de diagnóstico, para que `vcgencmd`
   esté disponible y F4 se pueda verificar.
5. Alineación de los métodos de verificación de los requisitos funcionales con
   lo que el acta exige y con lo que la imagen permite (D-27).
6. Limpieza de documentos: marcado de las mediciones preliminares de x86,
   renombrado del archivo de E4 superado, y eliminación de guiones obsoletos.
7. Habilitación del análisis de vulnerabilidades tras dos intentos fallidos
   (P-30).

**Aprendizajes**

- **El código duplicado entre el repositorio y la receta es una trampa
  silenciosa.** La receta consume una copia por `file://`, y nada advierte si
  esa copia quedó atrás. Un `diff -rq` periódico, o mejor aún migrar el
  `SRC_URI` a git con `SRCREV`, es lo que cierra el hueco.
- **Declarar no es instalar.** El packagegroup declara tres subpaquetes de
  `plugins-base` y la imagen instala treinta y ocho, incluyendo audio, OpenGL y
  salida a X11 en un sistema sin pantalla ni audio. Los `RDEPENDS` de los
  subpaquetes finos no los arrastran, así que entran por otro camino. Esa
  brecha entre lo declarado y lo instalado es, en sí misma, el resultado de un
  análisis de superficie de ataque.
- **Las clases de Yocto se reorganizaron en 5.x.** Están repartidas en
  `classes/`, `classes-global/` y `classes-recipe/`, con reglas distintas de
  uso. Seguir una guía de una versión anterior produce `Could not inherit file`
  sin pista de por qué.

---

## Estado del acta de validación

| Sección | Cumplidos | Pendientes |
|---|---|---|
| A · Caps | A2, A3, A4 | A1, A5, A6 — requieren regenerar con el pipeline real |
| B · Topología | B1, B2, B3, B4, B5, B6 | — |
| C · Hardware | C1, C3, C4 | **C2** — falta la mitad software |
| D · Latencia | D3, D4 parcial | D1, D2 — repetir en la placa |
| E · Errores | E1, E3, **E4**, **E6** | E2, E5 |
| F · Estabilidad | — | F1–F6 — requieren la corrida larga |
| G · Yocto | **G1**, **G2**, **G3**, **G5** | G4 — reconstrucción limpia |
| H · Acceso | H1, H2, H6, H7 | H3, H5 · H4 = N/A justificado |

---

## Pendientes

**Requieren la placa**

- [ ] C2: medir la ruta por software y calcular la razón (criterio de aceptación)
- [ ] F1–F4: corrida continua de 4 h con muestreo de salud
- [ ] H5: reiniciar con el buzzer conectado y verificar el silencio inicial
- [ ] G2: verificar que la tubería corre sobre la imagen de entrega
- [ ] E2, E5, H3: desconexión de cámara, disco lleno y las tres fallas

**No requieren la placa**

- [ ] G4: reconstrucción limpia sin `sstate-cache` siguiendo solo el tutorial.
      Depende de que el documento tutorial esté terminado: la prueba consiste
      en seguirlo al pie de la letra, de modo que no se puede validar antes.
- [ ] Análisis de SBOM/CVE de la imagen. El SPDX ya lo genera el build; falta
      el cruce contra la base de vulnerabilidades y la redacción del informe.

**Hallazgos documentados y no corregidos**

Los tres siguientes se detectaron, se entendió su causa y se decidió no
corregirlos por relación costo-beneficio frente al cronograma. Ninguno impide
el funcionamiento del sistema; los tres engordan la imagen.

- **P-20 · `opengl` activo en una placa sin pantalla.** Poky activa `opengl` por
  omisión, y eso arrastró Mesa y LLVM al árbol de compilación. Corregirlo
  (`DISTRO_FEATURES:remove = "opengl wayland x11"`) invalida todas las firmas
  de sstate y obliga a recompilar desde cero.
- **38 paquetes de `plugins-base` instalados con 3 declarados.** El packagegroup
  declara `-app`, `-videoconvertscale` y `-pango`, y la imagen trae además
  audio (`alsa`, `vorbis`, `theora`, `ogg`), OpenGL y salida a X11
  (`ximagesink`, `xvimagesink`). Verificado que los `RDEPENDS` de los
  subpaquetes finos **no** los arrastran: solo piden `gstreamer1.0`,
  `libgstapp-1.0` y `libgstvideo-1.0`. Entran por otra vía, probablemente la
  misma de P-20.
- **P-21 · El `PACKAGECONFIG` de OpenCV no redujo los módulos.** Se compilaron
  igual `gapi`, `tracking`, `xfeatures2d`, `stitching` y el resto de contrib.
  Sin resolver: queda pendiente revisar si dependen de otra variable o si la
  asignación no sobrescribió el `??=` de la receta.

---

## Resumen final

_(se completa al cierre del proyecto)_

- Horas totales dedicadas:
- Requerimientos verificados personalmente:
- Contribución principal al equipo:
- Qué haría distinto en un proyecto siguiente:
