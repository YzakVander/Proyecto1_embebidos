# Bitácora individual de trabajo

**Estudiante:** Daniel Chavarría García
**Rol en el equipo:** B — Plataforma (Yocto, BSP, imagen)
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
| GStreamer disponible | 1.28.2 |
| Directorio de compilación | `~/proyecto-acceso/build` |
| Capas | `~/proyecto-acceso/layers/` (enlaces a `~/taller-yocto/layers/`) |
| Hardware | RPi4 y microSD del laboratorio (sin acceso permanente); cámara **USB** autorizada por el profesor |

---

## Registro de decisiones de diseño

| # | Fecha | Decisión | Alternativas consideradas | Justificación |
|---|---|---|---|---|
| D-01 | 2026-09-10 | Usar `DISTRO = "poky"` | Build distro-less (solo oe-core) | meta-raspberrypi declara Poky como su foco principal de pruebas; además da una base conocida de `DISTRO_FEATURES` sobre la cual activar `gobject-introspection-data` |
| D-02 | 2026-09-10 | `INIT_MANAGER = "systemd"` | sysvinit | RF-11 (arranque automático) y RF-12 (reinicio ante falla) se resuelven con una unidad de servicio; el cierre ordenado del MP4 requiere `TimeoutStopSec` |
| D-03 | 2026-09-10 | Capas compartidas por enlace simbólico con `~/taller-yocto` | Clonar un árbol nuevo | Evita duplicar ~2 GiB de fuentes; los dos builds quedan independientes |
| D-04 | 2026-09-10 | Aceptar `synaptics-killswitch` en `LICENSE_FLAGS_ACCEPTED` | Excluir `packagegroup-base-extended` | `core-image-base` arrastra el firmware WiFi por diseño; el WiFi queda como respaldo si falla el cable en la demostración |
| D-05 | 2026-09-10 | Usar cámara **USB (UVC)** con `v4l2src`, excluir `libcamera` del packagegroup | Cámara CSI con `libcamerasrc` | El profesor autorizó cámara USB; elimina el riesgo técnico más alto (negociación de caps de `libcamerasrc`) y reduce el tamaño de la imagen. Agregar `libcamera` después es trivial si se consigue módulo CSI |
| D-06 | 2026-09-10 | Instalar conjuntos completos de plugins (`-good`, `-bad`) en la primera iteración | Seleccionar subpaquetes individuales desde el inicio | Primero confirmar que funciona; afinar hacia imagen mínima (RP-08) después. Optimizar antes de tener algo funcional impide saber qué rompió |
| D-07 | 2026-09-10 | Estrategia de trabajo: compilar en casa, verificar en laboratorio | Emulación con QEMU para todo | La RPi4 es del laboratorio y el acceso es intermitente; se prepara una imagen con el máximo de elementos verificables para aprovechar cada sesión presencial |

---

## Registro de tiempos de compilación

| Fecha | Objetivo | Inicio | Fin | Duración | Notas |
|---|---|---|---|---|---|
| 2026-09-10 | `core-image-base` | 11:09 | 23:17 | ~6 h efectivas | 5819 tareas, todas exitosas. Sstate previo solo aportó 5%: era de `qemux86-64` y las firmas incluyen arquitectura. Imagen: 98 MiB comprimidos |
| 2026-09-10 | `packagegroup-acceso` (dry-run) | — | — | ~2 min | 72% ya completo por reutilización del build anterior; ~1024 tareas nuevas pendientes |

---

## Registro de problemas y soluciones

| # | Fecha | Síntoma | Causa raíz | Solución | Tiempo perdido |
|---|---|---|---|---|---|
| P-01 | 2026-09-10 | `bitbake -e` sin salida y código 127 | Terminal nueva sin `oe-init-build-env`; el 127 de bash significa "comando no encontrado", no un fallo de Yocto | Re-ejecutar `source layers/openembeddedcore/oe-init-build-env build` | ~10 min |
| P-02 | 2026-09-10 | Fallo de parseo de `local.conf` | Comilla de apertura faltante en `SSTATE_DIR` y typo `sysyemd`; una comilla sin cerrar hace que BitBake lea el resto del archivo como cadena | Corrección con `sed`; verificación con `bitbake -e` antes de compilar | ~15 min |
| P-03 | 2026-09-10 | `Nothing RPROVIDES 'linux-firmware-rpidistro-bcm43456'` | Licencia restringida bloqueada por defecto (mecanismo de cumplimiento de Yocto) | `LICENSE_FLAGS_ACCEPTED += "synaptics-killswitch"` | ~5 min |
| P-04 | 2026-09-10 | Aviso: sstate compartido pero base de hashes local → sin reutilización | `BB_HASHSERVE_DB_DIR` apuntaba dentro del build | `BB_HASHSERVE_DB_DIR = "${SSTATE_DIR}"` | Detectado con `--dry-run` antes de compilar |
| P-05 | 2026-09-10 | Windows se congeló durante la compilación; `pgrep -c bitbake` devolvió 0 | Falso negativo: BitBake corre como procesos `python3`, no como ejecutable llamado `bitbake`. El congelamiento fue presión de memoria del anfitrión (475 MiB libres de 7.8 GiB), no fallo del build | Verificar con `pgrep -af bitbake`, `uptime` (load 7.2) y fecha de los `log.do_*`. La compilación nunca se detuvo | ~15 min de diagnóstico |
| P-06 | 2026-09-10 | `Nothing RPROVIDES 'gstremaer1.0-tools'` | Typo en `RDEPENDS` del packagegroup | `sed` de corrección | ~2 min |
| P-07 | 2026-09-10 | `Nothing RPROVIDES 'gstreamer1.0-tools'` **tras corregir el typo** | La receta `gstreamer1.0-tools` **no existe** en GStreamer 1.28.2; `gst-launch-1.0` y `gst-inspect-1.0` vienen dentro del paquete base `gstreamer1.0` | Eliminar la línea. Verificado con `bitbake-layers show-recipes "gstreamer1.0*"` | ~10 min |

---

## Entradas diarias

### 2026-09-10 · ___ h

**Objetivo de la sesión**

Preparar el árbol de capas y la configuración de compilación para
`raspberrypi4-64`, generar la primera imagen base y crear la primera receta
propia de la capa `meta-acceso`.

**Actividades**

1. Inventario del entorno: espacio, memoria, capas y caché disponibles.
2. Verificación de compatibilidad de serie entre capas (`LAYERSERIES_COMPAT`).
3. Creación de la capa `meta-acceso` con `bitbake-layers create-layer`.
4. Registro de ocho capas en `bblayers.conf`.
5. Configuración de `local.conf` y verificación con `bitbake -e`.
6. Validación previa con `bitbake core-image-base --dry-run`.
7. Compilación completa de `core-image-base` (5819 tareas).
8. Inspección de la imagen generada sin hardware: particiones, manifiesto, bootfiles.
9. Redacción de `packagegroup-acceso.bb`, primera receta propia.
10. Activación de `gobject-introspection-data` y `qemu-usermode`.

**Comandos relevantes**

```bash
source layers/openembeddedcore/oe-init-build-env build
bitbake-layers create-layer ../layers/meta-acceso
bitbake-layers add-layer ../layers/meta-raspberrypi
bitbake-layers show-layers
bitbake -e | grep -E "^(DISTRO|MACHINE|INIT_MANAGER)="
bitbake core-image-base --dry-run
bitbake core-image-base 2>&1 | tee /tmp/build-$(date +%Y%m%d-%H%M).log

# Inspección de la imagen sin hardware
fdisk -l /tmp/imagen.wic
grep -E "systemd|dropbear|openssh" *.manifest
ls bootfiles/

# Diagnóstico de nombres de paquetes
bitbake-layers show-recipes "gstreamer1.0*"
bitbake packagegroup-acceso --dry-run
```

**Resultados**

- Ocho capas registradas, todas compatibles con la serie `wrynose`.
- `core-image-base` compilada: 5819 tareas exitosas, imagen de 98 MiB.
- Particiones verificadas: FAT32 de 130 MB (arranque) + ext4 de 374 MB (raíz).
- systemd confirmado en el manifiesto, incluido `systemd-serialgetty`.
- **Hallazgo: la imagen NO incluye servidor SSH** → el primer arranque requiere
  monitor HDMI y teclado. Se agregará en la imagen del proyecto.
- `packagegroup-acceso` creada y resolviendo sin errores.

**Aprendizajes**

- `--dry-run` calcula el grafo completo de tareas sin ejecutarlas: detecta
  dependencias irresolubles y problemas de licencia antes de invertir horas.
- Las prioridades de capa determinan quién gana cuando dos definen la misma
  receta; el BSP usa 9 para poder sobrescribir recetas de oe-core.
- Un sstate compartido no se reutiliza si la base de equivalencia de hashes
  vive dentro del build.
- Las firmas de sstate incluyen la arquitectura del destino: caché de x86_64
  es casi inútil para un build ARM64 (5% de coincidencia).
- Un typo en `RDEPENDS` **no** se detecta al parsear — la receta es
  sintácticamente válida — solo al resolver el grafo de dependencias.
- Los nombres de paquetes cambian entre versiones de Yocto. Copiar listas de
  documentación antigua produce errores de `Nothing RPROVIDES`. Verificar
  siempre con `bitbake-layers show-recipes`.
- `python3-pygobject` por sí solo no habilita `import gi` con GStreamer:
  requiere los `.typelib`, que exigen `gobject-introspection-data` en
  `DISTRO_FEATURES` y `qemu-usermode` en `MACHINE_FEATURES` (la generación de
  introspección ejecuta binarios ARM64 bajo emulación durante el build).

**Pendientes**

- [ ] Escribir la receta de imagen `acceso-image.bb`
- [ ] Agregar servidor SSH a la imagen
- [ ] Compilar `acceso-image`
- [ ] Copiar imagen + balenaEtcher portable a llave USB (FAT32)
- [ ] Redactar guion de verificación para la sesión presencial
- [ ] Grabar microSD y verificar arranque en la RPi4 del laboratorio
- [ ] Optimizar el packagegroup hacia subpaquetes individuales (RP-08)

**Riesgos identificados**

| # | Riesgo | Estado |
|---|---|---|
| R-01 | El kit CanaKit no incluye cámara ni módulo de relé | **Mitigado parcialmente**: cámara USB autorizada por el profesor. Relé pendiente (sustituto posible: LED con resistencia en GPIO 27) |
| R-02 | Acceso intermitente a la RPi4 (equipo del laboratorio, sin fines de semana) | En gestión: se maximiza el contenido verificable por sesión presencial |

**Coordinación con el compañero**

- **Pendiente:** comunicar al Rol A que se usará **cámara USB** — cambia sus
  tuberías de `libcamerasrc` a `v4l2src`.
- **Pendiente:** solicitar al Rol A la lista de elementos de GStreamer que
  usa, para afinar el packagegroup hacia imagen mínima.
- **Pendiente:** acordar versión 1.0 del contrato de integración.

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
