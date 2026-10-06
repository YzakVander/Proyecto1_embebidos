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
| D-22 | 09-2_ | Buzzer pasivo en GPIO 18 por PWM de hardware | LEDs indicadores; conmutar el pin desde Python | El buzzer no oscila solo: necesita onda cuadrada. Conmutar a 2.5 kHz desde Python daría tono irregular y consumiría CPU que necesitan GStreamer y el codificador |
| D-23 | 09-2_ | Destino de transmisión automático: la Pi redirige el RTP a quien se conecte al canal TCP | IP fija en `acceso.conf` | El DHCP del laboratorio rota las direcciones cada ~30 min. Con IP fija, cada sesión empezaba reconfigurando el archivo en la placa |
| D-24 | 09-2_ | La revocación de credenciales es permanente, sin reactivación | Permitir reactivar una credencial dada de baja | Una credencial revocada puede estar circulando impresa o fotografiada. Reactivar el mismo identificador devolvería acceso a copias que se creían anuladas. Para readmitir a una persona se emite un identificador nuevo |
| D-25 | 10-02 | Dos recetas de imagen: `acceso-image` (entrega) y `acceso-image-dev` | Comentar las líneas de desarrollo antes de entregar | Comentar y descomentar es frágil: es lo que se olvida a última hora. La de desarrollo hereda de la de entrega y agrega las concesiones (G2) |
| D-26 | 10-02 | `RDEPENDS` de la aplicación a nivel de subpaquete, no al metapaquete | `RDEPENDS = "packagegroup-acceso"` | Si la receta se instala en otra imagen sin ese packagegroup, el paquete queda sin un solo plugin y el servicio muere en el arranque. La aplicación declara lo que necesita (G1) |
| D-27 | 10-02 | Ante la imposibilidad de usar `ffprobe` y `top -H` en la placa, se usa método equivalente y se documenta | Agregar `ffmpeg` y `procps` a la imagen | El acta busca verificar que el MP4 tenga índice y medir CPU por hilo durante 60 s; ambas cosas se logran con lo que la imagen trae (lectura de cajas MP4, `/proc/<pid>/stat`). Agregar las herramientas contradiría el principio de imagen mínima |
| **D-28** | **10-04, corregida 10-05** | **Sello de fecha y hora con `clockoverlay`, SOLO en la rama de codificación** | Marca de agua desde Python; sin sello | Insertado antes del codificador queda en los tres destinos: grabación, clips y transmisión. **La primera version lo puso en el `convertidor` de `acceso.conf`, que `pipeline.py` usa en las DOS ramas, y eso congelaba la tubería (P-32). Ahora `pipeline.py` lo filtra de la rama de QR**: el detector analiza la imagen para encontrar un código, sobreimprimirle texto es trabajo sin propósito |
| **D-29** | **10-05** | **Receta `red-acceso`: la configuración de red inalámbrica va EN LA IMAGEN** | Editar `/etc/wpa_supplicant/` a mano en la microSD tras cada grabado | La configuración manual se pierde en cada regrabado, y eso cuesta 15 min por iteración. Con dos redes conocidas y prioridad, la placa se conecta sola. Precio asumido: la contraseña queda versionada en claro, aceptable para el alcance del curso |
| **D-30** | **10-05** | **Zona horaria `America/Costa_Rica` en la imagen, con el enlace creado por la receta** | Dejar el sistema en UTC | Un registro de acceso con la hora equivocada no sirve como evidencia: el sello salía 6 h adelantado. `DEFAULT_TIMEZONE` **no basta** cuando se instala el subpaquete `tzdata-americas` suelto (P-38); el enlace lo crea `red-acceso` en `do_install` |

---

## Registro de tiempos de compilación

| Fecha | Objetivo | Duración | Notas |
|---|---|---|---|
| 09-10 | `core-image-base` | ~6 h | 5819 tareas. Sstate previo solo aportó 5%: era de `qemux86-64` |
| 09-23 | `acceso-control` | ~3.5 h | Mucho más de lo esperado para una receta que solo copia archivos: `RDEPENDS = packagegroup-acceso` arrastra GStreamer, Python y PyGObject completos |
| 09-23 | `opencv` (PACKAGECONFIG mínimo) | ~4 h | 3345 tareas. `do_compile` sola tomó la mayor parte |
| 10-02 | `acceso-image` con x264 | ~2 h | 7567 tareas, 7413 desde sstate |
| 10-04 | `acceso-image` + `acceso-image-dev` | ~15 min | 7644 tareas, 7601 desde sstate |
| **10-05** | **Cinco reconstrucciones incrementales** | **5–20 min c/u** | 7680 tareas, ~7640 desde sstate en cada una. Con sstate caliente y cambios acotados a la capa propia, el ciclo editar-compilar-grabar-probar baja a ~25 min |

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
| P-22 | 10-01 | Sin acceso a la placa: credenciales desconocidas | Imagen propia sin documentar la contraseña | Montar la microSD en la laptop e inspeccionar `/etc/shadow`: root tenía el campo de contraseña **vacío**, que funciona en consola pero **no por SSH** (dropbear y OpenSSH rechazan contraseñas vacías por diseño) | ~1 h |
| P-23 | 10-01 | `/etc/shadow` editado a mano quedó malformado | Dos puntos mal colocados al insertar el hash de `openssl passwd -6` | Comparar el formato campo por campo contra una línea sana; verificar el conteo con `awk -F:` antes de arrancar | ~20 min |
| P-24 | 10-02 | `gst-launch` externo falla con `Failed enabling i/p port, ret -3` y el kernel emite un WARNING en `vb2_start_streaming` | Los cinco nodos `/dev/video10,11,12,18,31` son el **mismo bloque** `bcm2835-codec`. La aplicación usa cinco contextos simultáneos (2 `v4l2jpegdec` + 2 `v4l2convert` + 1 `v4l2h264enc`) y no queda margen para un proceso externo | Descartadas por medición: CMA (512 MiB reservados, 507 libres), `gpu_mem` subido a 256 (falla igual a 640×480) y los tres modos de `io-mode`. Para medir a mano: detener el servicio y esperar ~10 s | **~2 h** |
| P-25 | 10-02 | El EOS no llegaba al bus: el último MP4 quedaba con `mdat` de 0 bytes y sin `moov` | Para llegar a `splitmuxsink` el EOS debe atravesar `v4l2jpegdec`, `v4l2convert` y `v4l2h264enc`, que al recibirlo vacían el bloque de hardware. En la RPi 4 ese vaciado no termina: el plazo de 10 s se agotaba siempre completo | Diagnóstico propio con `GST_DEBUG` y `kill -TERM` directo (descartando systemd). Corrección del Rol A: inyectar el EOS en la queue de grabación y esperar `splitmuxsink-fragment-closed`. **Cierre de 10 s → 10 ms** | **Defecto crítico** |
| P-26 | 10-02 | Tras un `kill -9`, el servicio reinicia y reporta PLAYING pero NO GRABA | El bloque `bcm2835-codec` queda en estado inservible. Segmentos de 595 B en vez de 17.4 MB/min, con el `ret -3` en `dmesg` como único síntoma | **Corregido el 10-05:** se verificó que un `systemctl restart` basta para recuperar; el reboot no es necesario. systemd cumple su parte (E6) pero la recuperación no es funcional sin ese reinicio del servicio | **Hallazgo** |
| P-27 | 10-02 | La receta de Yocto tenía código viejo: `retencion.py` ausente y cinco módulos desactualizados | La receta consume una **copia** de `app/` vía `file://`, y `sincronizar-receta.sh` no se había corrido antes de compilar. Nada lo advierte: el build pasa sin error | Encontrado por comparación sistemática (`diff -rq`) entre `app/acceso/` y la copia de la receta | **Error silencioso** |
| P-28 | 10-04 | La medición de F5 daba 645 MB/h y los segmentos pesaban 17.4 MB/min (~1050 MB/h) | Se midió el **crecimiento neto** de la carpeta, mientras la retención borraba en paralelo | Tres cifras distintas y válidas: neto 645 MB/h, escritura al dispositivo 710 MB/h, bruta ~1050 MB/h. La retención efectiva se calcula con la bruta | ~20 min |
| P-29 | 10-04 | `G2-dos-imagenes.txt` reportaba imágenes de 58 bytes | Se midió con `ls -lh` el **enlace simbólico**, no el archivo | `ls -lLh`. Tamaños reales: 159 MB (entrega) y 162 MB (desarrollo) | ~10 min |
| P-30 | 10-04 | `INHERIT += "cve-check"` y luego `"sbom-cve-check"` rompen el parseo de BitBake | En wrynose la clase se renombró a `sbom-cve-check` **y** vive en `classes-recipe/`, que solo se hereda desde una receta, no desde `local.conf` | Se activa con un **fragmento de configuración**, mecanismo nuevo de Yocto 5.x: `OE_FRAGMENTS += "core/yocto/sbom-cve-check"` | ~40 min |
| **P-31** | **10-05** | **Los clips de evento duraban 0.6 s en vez de 10 s: 19 cuadros de 450 disponibles** | `instantanea()` filtraba por `recibido_en`, el reloj de pared del momento en que el callback recibió el cuadro. Con `sync=false` el appsink entrega **en ráfagas**: si la tubería se atrasa y luego se pone al día, decenas de cuadros llegan con marcas casi idénticas aunque representen varios segundos de video | Filtrar por `pts_ns`, la marca de presentación que fija el codificador y mide tiempo de video. Además `todos.index(recientes[0])` compara por valor en un dataclass: sustituido por `len(todos) - len(recientes)`. **Verificado: 298 cuadros, 10.0 s, 3035 KiB** | **Defecto de evidencia** |
| **P-32** | **10-05** | **Con `clockoverlay`, la tubería se congela al minuto del arranque. El servicio sigue en `active`, el log dice PLAYING y no se graba nada. Sin un solo error** | `convertidor` de `acceso.conf` se inserta en las DOS ramas del `tee`, de modo que `clockoverlay` se instanciaba también en la del lector de QR. Pango levanta hilos de fontconfig que no terminan, la rama deja de consumir y el `tee` se bloquea. Síntoma en `/proc/<pid>/task`: dos hilos `[pango] fontcon` y **cuatro** `lector-qr` donde debería haber uno | Filtrar el `clockoverlay` de la rama de QR en `pipeline.py` con una expresión regular sobre `c.camara.convertidor`. Verificado: 18 MB/min sostenidos | **~3 h** |
| **P-33** | **10-05** | **El sello de hora se dibujaba como una fila de cuadros vacíos** | La imagen no tiene **ninguna** fuente instalada: `/usr/share/fonts/` vacío y `fc-list` sin resultados. Pango dibuja el recuadro y el fondo, pero sin tipografía no hay glifos. **No emite ningún error** | `ttf-dejavu-sans` en el packagegroup, junto a `gstreamer1.0-plugins-base-pango` que es quien lo usa. Nombre del **paquete**, no de la receta (ver P-35) | ~1 h |
| **P-34** | **10-05** | **`red-acceso` falla en `do_package`: "Didn't find service unit 'wpa_supplicant@wlan0.service'"** | `SYSTEMD_SERVICE` exige que la unidad la instale **esa misma receta**, y `wpa_supplicant@.service` pertenece al paquete `wpa-supplicant` | Quitar `SYSTEMD_SERVICE` y crear el enlace en `multi-user.target.wants` dentro de `do_install`, que es lo que `systemctl enable` hace de todos modos | ~20 min |
| **P-35** | **10-05** | **`Nothing RPROVIDES 'ttf-dejavu'` y antes `'gstreamer1.0-plugins-ugly-x264'`** | Confusión entre el nombre de la **receta** y el del **paquete**. `ttf-dejavu` es la receta; genera `ttf-dejavu-sans`, `-serif`, `-mono`. Y `plugins-ugly-x264` no existía hasta habilitar su `PACKAGECONFIG` | Consultar `bitbake -e <receta> \| grep ^PACKAGES=` antes de declarar nada en `RDEPENDS` | ~30 min |
| **P-36** | **10-05** | **`bmaptool` "graba" en 1 minuto y la Pi arranca con la imagen vieja** | La microSD no estaba conectada. `bmaptool` avisa `"/dev/sdb" does not exist, creating a regular file` y escribe 523 MB en un **archivo** llamado `/dev/sdb` | Verificar siempre antes de grabar: `[ -b /dev/sdb ] \|\| abortar`. Ocurrió dos veces | ~30 min |
| **P-37** | **10-05** | **`REMOTE HOST IDENTIFICATION HAS CHANGED` tras cada regrabado** | Cada imagen genera llaves de host SSH nuevas, y el cliente las tiene memorizadas de la tarjeta anterior | `ssh-keygen -f ~/.ssh/known_hosts -R <ip>`. Paso obligatorio del procedimiento de grabado | ~5 min |
| **P-38** | **10-05** | **El sello mostraba 23:21 cuando eran las 17:21 locales** | La imagen no incluye `tzdata`: `/usr/share/zoneinfo/` sin datos, `/etc/localtime` ausente, el sistema solo conoce UTC. **El reloj estaba bien** (systemd-timesyncd sincroniza por NTP); lo que faltaba era la zona | `tzdata-americas` en el packagegroup. **`DEFAULT_TIMEZONE` no basta**: con el subpaquete suelto no crea el enlace, hay que hacerlo en `do_install` de `red-acceso`. Verificado de fábrica: `18:41 CST` / `00:41 UTC` | ~1 h |
| **P-39** | **10-05** | **Durante RECOLECTAR la transmisión en vivo se congela en el puesto** | El `scp` satura el enlace inalámbrico y el flujo RTP, que va por UDP sobre la misma red, pierde cuadros. **La placa no se detiene**: los segmentos siguieron cerrándose cada 60 s durante toda la copia | No es un defecto del sistema sino del ancho de banda. Para la demostración: recolectar al final, como paso aparte, o usar cable Ethernet | Observación |

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
puede quedar inservible. El procedimiento de recuperación funciona, pero cuesta
una hora que no debería gastarse. Este episodio motivó la decisión D-25.

---

### 2026-10-02 — Verificación sistemática contra el acta (sesión larga)

**Objetivo.** Contrastar el estado real del proyecto contra los 44 ítems del
acta de validación, ejecutando en la placa todo lo pendiente del lado de
plataforma.

**Punto de partida.** 11 ítems cumplidos, ninguno de los siete criterios de
aceptación cerrado. El diagnóstico fue que **casi toda la evidencia estaba
medida en x86_64 con `videotestsrc`**, no en la plataforma final. No había
certeza de que el sistema corriera de verdad en la Raspberry.

**Lo que se cerró:** C1, G3, G5, E6, F5, E4 y RF-7.

**Los tres hallazgos de la sesión** están registrados como P-24, P-25 y P-26.
El de mayor valor fue el del EOS: se descartaron por medición las tres
hipótesis que apuntaban al elemento de GStreamer y se acotó la causa a la
cadena V4L2. El Rol A implementó la corrección y la verificación posterior
mostró el cierre pasando de 10 s agotados a **10 ms**, con `mdat` de 12 MB y
`moov` presente.

**Lo que no se pudo cerrar.** C2 quedó a medias: **no había ningún codificador
H.264 por software en la imagen**, de modo que no había con qué comparar. Eso
dejó ver además que la contingencia prevista en el plan de trabajo ("cambiar a
`x264enc`, una línea en `acceso.conf`") **no era ejecutable**.

**Aprendizajes**

- **Un síntoma puede tener una causa que no está donde apunta.** El `ret -3`
  parecía un driver roto; `v4l2-ctl` demostró que el hardware funcionaba.
- **Descartar hipótesis por medición vale tanto como confirmarlas.** CMA,
  `gpu_mem` y los tres modos de `io-mode` se descartaron con datos.
- **Un servicio "activo" no es un servicio que funciona.** Tras el `kill -9`,
  systemd reportaba `active (running)` y el log decía PLAYING mientras no se
  grababa nada. Vigilar el proceso no alcanza; hay que vigilar su producto.

---

### 2026-10-04 — Plataforma: G1, G2, sincronización y entregables

**Objetivo.** Cerrar los ítems de Yocto que no dependen de la placa y poner al
día la documentación.

**Qué se hizo.** G1 con el `RDEPENDS` a nivel de subpaquete (D-26), descubriendo
que `python3-numpy` no estaba declarado en ninguna parte. G2 con las dos recetas
de imagen (D-25), verificado con los manifiestos. P-27, la receta
desincronizada. `raspi-utils` para que `vcgencmd` esté disponible. Alineación de
los métodos de verificación de los requisitos funcionales (D-27). Limpieza de
documentos obsoletos. Y el análisis de vulnerabilidades tras dos intentos
fallidos (P-30).

**Aprendizajes**

- **El código duplicado entre el repositorio y la receta es una trampa
  silenciosa.** Un `diff -rq` periódico, o migrar el `SRC_URI` a git con
  `SRCREV`, es lo que cierra el hueco.
- **Declarar no es instalar.** El packagegroup declara tres subpaquetes de
  `plugins-base` y la imagen instala treinta y ocho. Esa brecha es, en sí
  misma, el resultado de un análisis de superficie de ataque.
- **Las clases de Yocto se reorganizaron en 5.x**, repartidas en `classes/`,
  `classes-global/` y `classes-recipe/`, con reglas distintas de uso.

---

### 2026-10-05 — Puesta en marcha completa sobre la placa

**Objetivo.** Correr el sistema entero sobre la imagen definitiva, verificar
los cinco casos de uso de punta a punta, y cerrar los ítems del acta que
quedaban del lado de plataforma.

**Lo que se cerró**

| Ítem | Resultado |
|---|---|
| **C2** | **Razón hardware/software = 369×** (0.8 % contra 295.0 %). Criterio del acta: ≥ 5× |
| **F4** | `throttled=0x0` en todas las muestras, 46–47 °C contra el umbral de 80 |
| **F5** | Caudal 614 MB/h con el pipeline grabando, `iostat -x`, 9712 MB libres contra 6500 de topes |
| **H5** | PWM sin exportar y `pinctrl get 18` → `a5 pd \| lo` con el servicio detenido. Silencio verificado al arranque |
| **E2** | Desconexión en caliente: 9 reintentos cada 5 s y `camara reconectada`. La numeración de segmentos no se repite |
| **H3 caso 1** | Sin cámara el sistema sigue atendiendo: la solicitud venció y se **denegó por omisión** |
| **RF-12/13/14** | Flujo completo de QR con los seis casos y latencias por rol |

**Las cuatro correcciones aplicadas**

1. **Buffer circular por `pts`** (P-31): los clips pasaron de 0.6 s a 10.0 s.
2. **`clockoverlay` fuera de la rama de QR** (P-32): la tubería dejó de
   congelarse al minuto.
3. **Receta `red-acceso`** (D-29): WiFi con dos redes conocidas, configurado en
   la imagen y verificado arrancando solo.
4. **Zona horaria** (D-30, P-38): `tzdata-americas` más el enlace
   `/etc/localtime` creado por la receta.

**La prueba del sistema completo**

Verificados en una sola sesión: transmisión en vivo con sello de fecha y hora
legible (CU-1), RECOLECTAR con evidencia, clips, bitácora, QR activos y MP4
continuo (CU-2), solicitud y decisión desde el puesto (CU-3), alta de
credenciales (CU-11), y baja, listado y regeneración (CU-12).

RF-13 con las latencias que separan los roles de forma medible:

| Caso | Resultado | Latencia |
|---|---|---|
| mantenimiento | permitido | **0.4 ms** — automático |
| visitante | permitido | 5344.7 ms — decide el vigilante |
| visitante | denegado | 5314.0 ms |
| QR no registrado | denegado | 5100.8 ms |
| sin respuesta | denegado_por_vencimiento | 30001.4 ms |

Los 0.4 ms del rol mantenimiento contra los ~5000 de visitante demuestran la
diferencia con números, no con una descripción.

**Aprendizajes**

- **Lo que una imagen mínima no incluye no produce errores, produce
  comportamientos silenciosamente incorrectos.** Cuatro casos el mismo día:
  sin fuentes el sello sale en blanco, sin `tzdata` la hora queda 6 h
  adelantada, sin el overlay de PWM el buzzer no suena, y `clockoverlay` en la
  rama equivocada congela la tubería. Ninguno emite un mensaje de error. El
  único modo de encontrarlos es mirar el resultado, no el log.
- **El nombre de una receta no es el nombre de su paquete.** `ttf-dejavu` es la
  receta; `ttf-dejavu-sans` es el paquete. Dos compilaciones perdidas por eso
  (P-35). `bitbake -e <receta> | grep ^PACKAGES=` lo resuelve en segundos.
- **Escribir en un dispositivo que no existe no da error.** `bmaptool` crea un
  archivo normal y reporta éxito (P-36). Verificar con `[ -b /dev/sdX ]` antes
  de grabar debe ser parte del procedimiento, no una precaución opcional.
- **Un pipeline multimedia puede fallar sin que ningún componente falle.** En
  P-32 cada elemento funcionaba; lo que se rompía era la coordinación entre
  ramas de un `tee`, porque una de ellas dejaba de consumir. Ese tipo de fallo
  no aparece inspeccionando elementos de a uno.

---

## Estado del acta de validación

| Sección | Cumplidos | Pendientes |
|---|---|---|
| A · Caps | A2, A3, A4 | A1, A5, A6 — del Rol A, regenerar con el pipeline real |
| B · Topología | B1, B2, B3, B4, B5, B6 | — |
| C · Hardware | C1, **C2**, C3, C4 | — |
| D · Latencia | D3, D4 parcial | D1, D2 — del Rol A |
| E · Errores | E1, **E2**, E3, E4, E6 | E5 |
| F · Estabilidad | **F4**, **F5** | F1, F2, F3, F6 — requieren la corrida larga |
| G · Yocto | G1, G2, G3, **G4**, G5 | — |
| H · Acceso | H1, H2, **H5**, H6, H7 | H3 casos 2 y 3 · H4 = N/A justificado |

**Criterios de aceptación: cinco de siete cerrados** — razón de CPU ≥ 5×,
`get_throttled = 0x0`, último archivo reproducible, grafo .dot pendiente (Rol A)
y reconstrucción desde cero verificada.

---

## Pendientes

**Requieren la placa**

- [ ] E5: llenar el disco con `fallocate` y observar el comportamiento
- [ ] H3 casos 2 y 3: proceso colgado con `kill -STOP` y corte de energía
- [ ] F1–F3, F6: corrida continua de 4 h con muestreo de salud

**No requieren la placa**

- [ ] Informe de SBOM/CVE: el SPDX ya lo genera el build y el análisis está
      redactado; falta el cruce automático contra la base de vulnerabilidades,
      cuya descarga del índice del NIST no completó en dos intentos
- [ ] Declaración de uso de IA: falta la parte del Rol A
- [ ] Ensayo cronometrado de la demostración, dos veces

**Hallazgos documentados y no corregidos**

Se detectaron, se entendió su causa y se decidió no corregirlos por relación
costo-beneficio frente al cronograma. Ninguno impide el funcionamiento; los
tres engordan la imagen.

- **P-20 · `opengl` activo en una placa sin pantalla.** Poky lo activa por
  omisión y eso arrastró Mesa y LLVM. Corregirlo invalida todas las firmas de
  sstate y obliga a recompilar desde cero.
- **38 paquetes de `plugins-base` instalados con 3 declarados**, incluyendo
  audio y salida a X11 en un sistema que no tiene ninguna de las dos cosas.
  Verificado que los `RDEPENDS` de los subpaquetes finos **no** los arrastran:
  entran por otra vía, probablemente la misma de P-20.
- **P-21 · El `PACKAGECONFIG` de OpenCV no redujo los módulos.** Queda
  pendiente revisar si dependen de otra variable o si la asignación no
  sobrescribió el `??=` de la receta.

**Riesgos conocidos para la demostración**

- Tras una terminación anormal del proceso, el servicio reinicia pero no graba
  hasta un `systemctl restart` adicional (P-26). Conviene reiniciar el servicio
  justo antes de empezar.
- RECOLECTAR satura el enlace inalámbrico y congela la vista en vivo (P-39).
  Dejarlo para el final o usar cable Ethernet.
- El punto de acceso del teléfono se apaga si no detecta clientes. Mantener la
  laptop conectada, o usar cable.

---

## Resumen final

_(se completa al cierre del proyecto)_

- Horas totales dedicadas:
- Requerimientos verificados personalmente:
- Contribución principal al equipo:
- Qué haría distinto en un proyecto siguiente:
