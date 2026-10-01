# Bitácora individual de trabajo

**Estudiante:** Daniel Chavarría García
**Rol en el equipo:** B — Plataforma (Yocto, BSP, imagen) · asumió temporalmente el Rol A mientras el compañero no tuvo disponibilidad
**Proyecto 1 — Sistema de control de acceso con Yocto Project y GStreamer**
**Taller de Sistemas Embebidos · TEC · II Semestre 2026**
**Prof. Dr. Ing. Johan Carvajal Godínez**

---

## Entorno de trabajo

| Elemento | Valor |
|---|---|
| Host | WSL2 · Ubuntu 24.04 sobre Windows (DESKTOP-R72NF1I) |
| RAM / swap | 7.6 GiB / 8 GiB |
| Yocto | Poky / oe-core `yocto-6.0.2` (serie Wrynose) |
| BitBake | 2.18.0 |
| Máquina destino | `raspberrypi4-64` (`TUNE_FEATURES = aarch64 crc cortexa72 nocrypto`) |
| GStreamer en la imagen | 1.28.2 |
| GStreamer en el host (desarrollo) | 1.24.2 |
| Python en la imagen | 3.14 |
| OpenCV en la imagen | 4.13.0 (`python3-opencv`) |
| Directorio de compilación | `~/proyecto-acceso/build` |
| Aplicación (Rol A) | `~/proyecto-acceso/app` |
| Capa propia | `~/proyecto-acceso/meta-acceso` (enlazada desde `layers/`) |
| Repositorio | `github.com/YzakVander/Proyecto1_embebidos`, rama `Daniel` |
| Hardware | RPi4 y microSD del laboratorio (acceso intermitente); cámara **USB** autorizada por el profesor |

---

## Registro de decisiones de diseño

| # | Fecha | Decisión | Alternativas consideradas | Justificación |
|---|---|---|---|---|
| D-01 | 09-10 | `DISTRO = "poky"` | Build distro-less | meta-raspberrypi declara Poky como su foco de pruebas; base conocida de `DISTRO_FEATURES` |
| D-02 | 09-10 | `INIT_MANAGER = "systemd"` | sysvinit | RF-11 y RF-12 se resuelven con una unidad; el cierre ordenado del MP4 requiere `TimeoutStopSec` |
| D-03 | 09-10 | Capas por enlace simbólico con `~/taller-yocto` | Clonar árbol nuevo | Evita duplicar ~2 GiB; los builds quedan independientes |
| D-04 | 09-10 | Aceptar `synaptics-killswitch` | Excluir `packagegroup-base-extended` | `core-image-base` arrastra el firmware WiFi por diseño |
| D-05 | 09-10 | Cámara **USB (UVC)** con `v4l2src` | CSI con `libcamerasrc` | Autorizado por el profesor; elimina el riesgo técnico más alto |
| D-06 | 09-10 | Conjuntos completos de plugins en la 1.ª iteración | Subpaquetes desde el inicio | Primero funcionar, después afinar (RP-08) |
| D-07 | 09-10 | Compilar en casa, verificar en laboratorio | QEMU para todo | Acceso intermitente a la RPi4 |
| D-08 | 09-19 | `appsink` con búfer circular de pre-evento | `split-now` sobre `splitmuxsink`; cuadro único | El clip necesita contexto ANTES del evento: una cámara de vigilancia real hace pre-roll |
| D-09 | 09-19 | Guardar cuadros H.264 comprimidos, no crudos | Cuadros I420 en RAM | 10 s comprimidos = 235 KiB medidos, contra ~415 MB crudos. Precio: recortar en cuadro clave |
| D-10 | 09-19 | Ventana del clip: 5 s antes + 5 s después | 3+2 | Más contexto para auditar; con cuadros comprimidos el costo en RAM es irrelevante |
| D-11 | 09-19 | E3: reconectar con alerta, no morir | Morir y que systemd reinicie | El checklist acepta ambas pero exige decidir. Reintentos indefinidos cada 5 s |
| D-12 | 09-19 | H2: plazo de 30 s, vencimiento DEFINITIVO | 5 s, 10 s | 30 s da margen a una persona real (latencias medidas: 6.8 s y 15.9 s) |
| D-13 | 09-19 | H6: archivo JSONL con `fsync` | journald | Un archivo se inspecciona con `cat`; `fsync` lo protege de corte de energía |
| D-14 | 09-19 | B4/B5 se CUMPLEN, no se declaran N/A | Declararlos no aplicables | Único N/A legítimo: **H4** (no hay cerradura física, solo LED indicadores) |
| **D-15** | **09-23** | **Desglosar `packagegroup-acceso` a subpaquetes derivados de la tubería real** | Mantener los conjuntos completos `-good`/`-bad` | Cumple G1 y RP-08. La lista **no se adivinó**: se obtuvo mapeando cada elemento de la tubería a su biblioteca con `gst-inspect-1.0 \| grep Filename`, y de ahí al subpaquete |
| **D-16** | **09-23** | **`videotestsrc` y las herramientas van en `-diagnostico`, fuera del núcleo** | Un solo paquete con todo | La imagen de producción no debe llevar la fuente de prueba usada en desarrollo (G2) |
| **D-17** | **09-23** | **SSH (dropbear) en la imagen** | Imagen sin acceso remoto | Permite iterar el código Python con `scp` + `systemctl restart` sin regenerar la imagen. Sin esto, cada cambio costaría una compilación completa |
| **D-18** | **09-23** | **Instalación manual en `do_install` en vez de `inherit setuptools3`** | Empaquetado PEP 517 | Ocho módulos sin dependencias de compilación; `setuptools3` agregaría `python3-setuptools-native` al build sin aportar nada |
| **D-19** | **09-23** | **OpenCV para la lectura de QR** | `zbar` (mucho más liviano) | Requisito del proyecto. Se asume el costo: ~4 h de compilación y varios cientos de MiB |
| **D-20** | **09-23** | **El QR separa identificación de autorización** | Sustituir al vigilante por el QR | El lector **identifica**; el vigilante **autoriza**. Si el QR no resuelve (ilegible o no autorizado), escala al vigilante con el plazo de H2. El vigilante pasa de único camino a excepción, como en un control de acceso real |
| **D-21** | **09-23** | **El reconocimiento de QR corre en la RPi4, no en el puesto de vigilancia** | Procesar en la máquina receptora | Un control de acceso que depende de que el puesto remoto esté conectado para abrir la puerta es frágil. La Pi decide sola e informa |

---

## Registro de tiempos de compilación

| Fecha | Objetivo | Inicio | Fin | Duración | Notas |
|---|---|---|---|---|---|
| 09-10 | `core-image-base` | 11:09 | 23:17 | ~6 h efectivas | 5819 tareas. Sstate previo solo aportó 5%: era de `qemux86-64` |
| 09-10 | `packagegroup-acceso` (dry-run) | — | — | ~2 min | 72% completo; ~1024 tareas nuevas pendientes |
| **09-23** | **`acceso-control`** | ___ | **15:06** | **~3.5 h** | Mucho más de lo esperado para una receta que solo copia archivos: `RDEPENDS = packagegroup-acceso` arrastra GStreamer, Python y PyGObject completos |
| **09-23** | **`opencv` (PACKAGECONFIG mínimo)** | **~15:33** | **19:36** | **~4 h** | 3345 tareas. `do_compile` sola tomó la mayor parte; BitBake emite "still alive" cada 600 s cuando una tarea es larga |

---

## Registro de problemas y soluciones

| # | Fecha | Síntoma | Causa raíz | Solución | Tiempo |
|---|---|---|---|---|---|
| P-01 | 09-10 | `bitbake -e` sin salida, código 127 | Terminal nueva sin `oe-init-build-env`; 127 = comando no encontrado | Re-ejecutar el `source` | ~10 min |
| P-02 | 09-10 | Fallo de parseo de `local.conf` | Comilla sin abrir en `SSTATE_DIR` y typo `sysyemd` | `sed` + verificación con `bitbake -e` | ~15 min |
| P-03 | 09-10 | `Nothing RPROVIDES 'linux-firmware-rpidistro-bcm43456'` | Licencia restringida bloqueada por defecto | `LICENSE_FLAGS_ACCEPTED` | ~5 min |
| P-04 | 09-10 | Sstate compartido sin reutilización | `BB_HASHSERVE_DB_DIR` dentro del build | Apuntarlo a `${SSTATE_DIR}` | Detectado con `--dry-run` |
| P-05 | 09-10 | Windows congelado; `pgrep -c bitbake` = 0 | Falso negativo: BitBake corre como `python3` | `pgrep -af`, `uptime`, fecha de los `log.do_*` | ~15 min |
| P-06 | 09-10 | `Nothing RPROVIDES 'gstremaer1.0-tools'` | Typo en `RDEPENDS` | `sed` | ~2 min |
| P-07 | 09-10 | Mismo error tras corregir el typo | La receta `gstreamer1.0-tools` **no existe** en 1.28.2 | Eliminar la línea | ~10 min |
| P-08 | 09-19 | `x264enc` producía perfil `high-4:4:4` | El `capsfilter` no fijaba el formato de píxel | Añadir `format=I420` | ~20 min |
| P-09 | 09-19 | `fpsdisplaysink` no imprimía nada | En 1.24 dejó de escribir a stdout | Medir tiempo total en vez de contar cuadros | ~30 min |
| P-10 | 09-19 | Un `PERMITIR` tardío era aceptado tras el vencimiento | `esperar()` devolvía VENCIDO pero no cerraba la solicitud | Fijar el resultado y marcar el `Event` bajo lock | **Error crítico** |
| P-11 | 09-19 | Clip de 10 s salía corto | El búfer se dimensionaba solo con `segundos_antes` | Dimensionar con `antes + despues` | ~10 min |
| P-12 | 09-19 | `mp4mux`: "Buffer has no PTS" | Flujo elemental sin marcas de tiempo | `ffmpeg -r 30 -i ... -c copy` | ~25 min |
| P-13 | 09-19 | El clip no era Annex B: empezaba en `00 00 00 02` | `h264parse` entregaba formato `avc` | Diagnosticado con `xxd`. Ver P-14 | ~15 min |
| P-14 | 09-19 | `not-negotiated` en bucle al añadir `capsfilter` | Un `tee` impone las mismas caps a TODAS sus ramas | Segundo `h264parse` en la rama del `appsink` | ~20 min |
| P-15 | 09-19 | Push rechazado: "fetch first" | La rama remota tenía commits hechos desde la web | `git pull --rebase origin Daniel` | ~10 min |
| **P-16** | **09-23** | **Los módulos Python quedaron instalados en `/acceso/`, en la raíz del sistema de archivos** | **`${PYTHON_SITEPACKAGES_DIR}` se expandió VACÍA: la receta no heredaba `python3-dir`.** BitBake no advierte de variables indefinidas y `/acceso` es una ruta válida; el QA tampoco lo detectó porque `FILES` se expandió igual | `inherit systemd python3-dir`. Verificado con `bitbake -e \| grep ^PYTHON_SITEPACKAGES_DIR=` y reinspección del directorio `image/` | **Error silencioso** |
| **P-17** | **09-23** | **`Nothing RPROVIDES 'python3-libgpiod'`** | El paquete no existe con ese nombre; `PACKAGES` de `libgpiod` no incluye enlaces de Python y la receta no expone un `PACKAGECONFIG[python3]` en esta versión | Se retira del packagegroup. La aplicación ya cae al backend simulado si falta `gpiod`; para el destino queda `libgpiod-tools` (`gpioset`) | ~15 min |
| **P-18** | **09-23** | **`Nothing RPROVIDES 'ffmpeg'`** | Licencia `commercial`, bloqueada por defecto | Se retira: `ffmpeg` se usa en la PC de desarrollo para convertir clips, no en la Raspberry. Error de alcance, no de configuración | ~5 min |
| **P-19** | **09-23** | **Segunda terminal: "No reply from server", reconexión en bucle** | **BitBake usa un único servidor por directorio de build.** La primera terminal lo tenía ocupado compilando | No es un error: es exclusión mutua. Para consultar metadatos mientras se compila, leer las recetas directamente con `grep` en vez de usar `bitbake-layers` | ~5 min |
| **P-20** | **09-23** | **El build arrastró `mesa` y `llvm-native`, horas de compilación** | Cadena `gstreamer1.0-plugins-base → opengl (activado por Poky) → mesa → llvm`. **La aplicación no usa OpenGL**: codifica, transmite y graba sin mostrar nada | Detectado, no corregido aún: cambiar `DISTRO_FEATURES` invalida firmas y obliga a recompilar. Pendiente para la imagen mínima: `DISTRO_FEATURES:remove = "opengl wayland x11"` | Hallazgo |
| **P-21** | **09-23** | **`PACKAGECONFIG:pn-opencv = "python3"` no redujo los módulos compilados** | Se generaron igual `gapi`, `tracking`, `xfeatures2d`, `stitching`, `face` y el resto de contrib | Sin resolver. Pendiente revisar si esos módulos dependen de otra variable o si la asignación no sobrescribió el `??=` | Pendiente |

---

## Entradas diarias

### 2026-09-10 · ___ h — Plataforma: árbol de capas e imagen base

_(entrada previa sin cambios — ver historial del repositorio)_

---

### 2026-09-19 · ___ h — Aplicación: pipeline, búfer circular y decisión de acceso

_(entrada previa sin cambios — ver historial del repositorio)_

**Resumen:** diseño y validación de la tubería GStreamer, implementación de los
ocho módulos de la aplicación en Python, pruebas unitarias y ejecución de los
tres casos de uso con evidencia medida. 21 de 44 ítems del checklist cerrados.

---

### 2026-09-2_ · ___ h — Revisión con el profesor

**Objetivo:** presentar casos de uso, requisitos y el estado de la lista de
verificación del pipeline.

_(completar: qué se presentó, observaciones recibidas, qué se acordó corregir)_

---

### 2026-09-23 · ___ h — Plataforma: empaquetado, imagen y OpenCV

**Objetivo de la sesión**

Convertir la aplicación validada en un paquete que la imagen instale y systemd
arranque solo, desglosar las dependencias a nivel de subpaquete (G1), y
compilar OpenCV para habilitar la lectura de códigos QR.

**Actividades**

1. Derivación de la lista real de plugins: cada elemento de la tubería mapeado
   a su biblioteca con `gst-inspect-1.0 | grep Filename`, y de ahí al subpaquete.
2. Reescritura de `packagegroup-acceso.bb` con subpaquetes individuales (G1) y
   separación del bloque de diagnóstico (G2).
3. Redacción de `acceso-control_1.0.bb`: instalación manual, `CONFFILES`,
   `RDEPENDS` al packagegroup.
4. Unidad systemd con `Restart=on-failure`, `RestartSec=5`, `TimeoutStopSec=20`,
   `StateDirectory` y `RuntimeDirectory` (E6, E4).
5. Script `sincronizar-receta.sh` para mantener al día la copia de `app/` que
   la receta consume vía `file://`.
6. Compilación de `acceso-control`, diagnóstico y corrección de P-16.
7. Merge de `origin/main` con los cambios del compañero; resincronización.
8. Redacción de `acceso-image.bb` con SSH (dropbear).
9. Configuración y compilación de OpenCV 4.13.0 con `python3-opencv`.
10. Prueba de cámara y de transmisión en vivo hacia la computadora del compañero.

**Comandos relevantes**

```bash
# G1 - derivar la lista de plugins de la tuberia real
gst-inspect-1.0 <elemento> | grep -m1 Filename

# Diagnostico de P-16
bitbake -e acceso-control | grep ^PYTHON_SITEPACKAGES_DIR=
find tmp/work/*/acceso-control/*/image -type f | sed 's|.*/image||'
cat tmp/work/*/acceso-control/*/temp/log.do_package_qa | grep -iE "WARNING|ERROR"

# OpenCV
echo 'PACKAGECONFIG:pn-opencv = "python3"' >> conf/local.conf
bitbake opencv
find tmp/work/*/opencv/*/image -name "cv2*"

# Integracion con el Rol A
git merge origin/main
./scripts/sincronizar-receta.sh
```

**Resultados**

Empaquetado verificado, con rutas correctas tras corregir P-16:

```
/usr/bin/acceso-control
/etc/acceso/acceso.conf
/usr/lib/systemd/system/acceso-control.service
/usr/lib/python3.14/site-packages/acceso/{8 módulos}
```

`log.do_package_qa` sin advertencias ni errores.

OpenCV compilado y empaquetado:

```
python3-opencv-4.13.0-r0.cortexa72.rpm            2.3 MB
libopencv-objdetect413-...rpm                    573 KB   ← QRCodeDetector
/usr/lib/python3.14/site-packages/cv2/python-3.14/cv2.cpython-314-aarch64-linux-gnu.so
```

**Cámara y transmisión en vivo**

_(completar con los datos concretos)_

- Fuente de video utilizada: ___
- Caps negociadas por la cámara: ___
- Máquina emisora: ___ · Máquina receptora: ___
- Red utilizada: ___ · IP destino: ___ · Puerto: 5000/UDP
- Resultado: transmisión en vivo verificada de extremo a extremo

**Aprendizajes**

- **Una variable de clase no heredada se expande vacía sin producir error.**
  `${PYTHON_SITEPACKAGES_DIR}` sin `inherit python3-dir` dejó los módulos en la
  raíz del sistema de archivos, y el control de calidad no lo detectó porque
  `FILES` se expandió de la misma forma. El paquete era internamente
  coherente y completamente inútil. Solo se ve inspeccionando el directorio
  `image/` antes de construir la imagen.
- **G1 se cumple derivando, no adivinando.** El mapeo elemento → biblioteca →
  subpaquete reveló que `splitmuxsink` vive en `multifile` y no en `isomp4`,
  algo contraintuitivo que habría producido un `no element` en el destino
  después de una hora de compilación.
- **Los nombres de paquete no son estables entre versiones ni entre proyectos.**
  `gstreamer1.0-tools` y `python3-libgpiod` no existen en esta versión, y
  `ffmpeg` está bloqueado por licencia. El `--dry-run` los detecta en minutos;
  sin él aparecerían al final de una compilación larga.
- **Una imagen "mínima" no lo es por omisión.** Poky activa `opengl`, y esa
  sola feature arrastró Mesa y LLVM, horas de compilación para algo que un
  dispositivo sin monitor no usa. Saber por qué entró un paquete que la
  aplicación nunca invoca es parte de diseñar la imagen, no solo de compilarla.
- **El código Python no obliga a regenerar la imagen.** Con SSH en la imagen,
  el ciclo es `scp` + `systemctl restart`: segundos en vez de horas. Solo se
  recompila cuando cambia *qué paquetes* contiene la imagen. La disciplina
  necesaria es llevar de vuelta al repositorio todo lo que se edite en el
  destino, o la imagen y la Pi divergen.

**Estado del checklist**

| Sección | Cerrados | Pendientes |
|---|---|---|
| A · Caps | A1, A2, A4, A5, A6 | A3 |
| B · Topología | B1, B2, B3, B4, B5 | B6 |
| C · Hardware | C3 · C2 parcial | C1, C2, C4 — requieren RPi4 |
| D · Latencia | D1, D3, D4 | D2 |
| E · Errores | E1, E3, E4, **E6** | E2, E5 |
| F · Estabilidad | — | F1–F6 |
| G · Yocto | **G1** | G2, G3, G4, G5 |
| H · Acceso | H1, H2, H6 | H3, H5, H7 · H4 = N/A justificado |

**Pendientes**

- [ ] Compilar `acceso-image` con `python3-opencv`
- [ ] `gpio=27=op,dl` y `gpio=22=op,dl` en `RPI_EXTRA_CONFIG` (H5)
- [ ] Documento tutorial paso a paso (G5)
- [ ] Reconstrucción limpia sin `sstate-cache` (G4) — mayor riesgo de cronograma
- [ ] Quitar `opengl wayland x11` de `DISTRO_FEATURES` (RP-08)
- [ ] Verificar en la RPi4: C1, C2, F4, E2
- [ ] Revisar por qué el `PACKAGECONFIG` de OpenCV no redujo los módulos

**Coordinación con el compañero**

- Se integró su rama `main`: documentó línea por línea `config.py` y
  `pipeline.py`. **Verificado que la corrección de P-14 (`h264parse` en la rama
  del `appsink`) sobrevivió a su edición** — de haberse perdido, los clips
  volverían a salir en formato `avc` e irreproducibles.
- Se retiraron `app.zip` y `app.7z` del repositorio: duplicaban código ya
  versionado. Acordar que no se vuelvan a subir.
- **Entregado:** la lista de elementos GStreamer usados, base del packagegroup.
- **Informado:** OpenCV 4.13.0 estará disponible en la imagen, compilado **sin**
  soporte GStreamer. Los cuadros le llegan por el `appsink` y los convierte a
  NumPy él mismo.
- **Acordado (D-20):** el QR identifica, el vigilante autoriza. El lector escala
  al vigilante cuando no puede resolver.
- **Pendiente:** definir la rama de integración y la lista de usuarios autorizados.

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
