# Análisis de SBOM y superficie de ataque de la imagen

**Proyecto 1 — Sistema de control de acceso con Yocto Project y GStreamer**
Taller de Sistemas Embebidos · TEC · II Semestre 2026
Rol B — plataforma

---

## 1. Qué se generó y con qué

El build produce automáticamente el **SBOM en formato SPDX 3.0.1**, sin
configuración adicional: la tarea `do_create_image_sbom_spdx` forma parte del
flujo de Yocto wrynose.

| Artefacto | Ubicación | Tamaño |
|---|---|---|
| SBOM de la imagen de entrega | `tmp/deploy/spdx/3.0.1/raspberrypi4_64/rootfs/acceso-image-raspberrypi4-64-rootfs.spdx.json` | 2.0 MB |
| SBOM de la imagen de desarrollo | `…/acceso-image-dev-raspberrypi4-64-rootfs.spdx.json` | 2.1 MB |
| SBOM por paquete y por build | `…/common-package/`, `…/builds/`, `…/static/` | 428 MB en total |
| Manifiestos de paquetes | `app/mediciones/G2-manifest-entrega.txt`, `G2-manifest-dev.txt` | — |

**El cruce automático contra la base de vulnerabilidades no se completó.** La
clase `sbom-cve-check` se habilitó correctamente mediante el fragmento de
configuración `OE_FRAGMENTS += "core/yocto/sbom-cve-check"` (ver P-30 de la
bitácora), pero la tarea `do_fetch` del índice del NIST quedó bloqueada en dos
intentos sin completar la descarga. El análisis de este documento se construye
entonces sobre el inventario SPDX y los manifiestos, que es donde está el
contenido evaluable: **qué se instaló, por qué, y qué no hacía falta.**

---

## 2. Composición de la imagen

Conteo sobre el manifiesto de la imagen de entrega:

| Categoría | Paquetes | Proporción |
|---|---|---|
| Módulos del kernel (`kernel-module-*`) | **1 865** | **83 %** |
| Espacio de usuario | **390** | 17 % |
| **Total** | **2 255** | 100 % |

### Hallazgo 1 — el 83 % del inventario son módulos del kernel

El número de 2 255 paquetes es engañoso si se lee como medida de complejidad o
de superficie de ataque. La causa está en una sola línea de
`acceso-image.bb`:

    IMAGE_INSTALL:append = " ... kernel-modules ..."

`kernel-modules` instala **todos** los módulos compilados para la máquina, no
solo los que el sistema usa. Un control de acceso con una cámara USB, salida
PWM y red Ethernet necesita del orden de una decena de módulos: UVC, V4L2,
`bcm2835-codec`, `pwm-bcm2835`, el controlador de red y poco más.

El resto —controladores de tarjetas de sonido profesional, de adaptadores
inalámbricos de otros fabricantes, de sistemas de archivos que no se montan, de
protocolos de red que no se usan— se instala sin que nada lo requiera.

**Impacto en superficie de ataque.** Un módulo de kernel no cargado no es
explotable de forma directa, pero su presencia en disco permite que un atacante
con acceso local lo cargue (`modprobe`), y cada módulo es código del kernel con
su propio historial de vulnerabilidades. En un dispositivo empotrado de función
fija, instalar 1 865 módulos para usar diez es lo contrario de una imagen a la
medida.

**Corrección posible y por qué no se aplicó.** Sustituir `kernel-modules` por la
lista explícita de módulos necesarios reduciría drásticamente el inventario.
No se aplicó porque exige verificar en la placa qué módulos se cargan de verdad
(`lsmod` en operación), y la disponibilidad del hardware fue intermitente. Queda
documentado como la mejora de mayor impacto pendiente.

---

## 3. Composición del espacio de usuario

Las 390 entradas restantes, agrupadas por familia:

| Familia | Paquetes | Comentario |
|---|---|---|
| GStreamer | 47 | El marco multimedia y sus plugins |
| OpenCV | 42 | Requisito del proyecto para la lectura de QR |
| Python 3 | 35 | Intérprete y módulos de la biblioteca estándar |
| packagegroup | 23 | Agrupadores, sin contenido propio |
| util-linux, systemd, PAM, e2fsprogs… | ~60 | Base del sistema |
| libxcb, alsa | 14 | **No los usa la aplicación** — ver hallazgo 3 |
| Resto | ~163 | Bibliotecas de soporte |

### Hallazgo 2 — el packagegroup fino funciona, y se puede medir

El `packagegroup-acceso` declara subpaquetes individuales en vez de los
conjuntos completos `-good`, `-bad` y `-base`. La lista no se adivinó: se
derivó mapeando cada elemento de la tubería a su biblioteca con
`gst-inspect-1.0 | grep Filename`, y de ahí al subpaquete que la contiene.

Para dimensionar el ahorro: el conjunto completo `gstreamer1.0-plugins-good`
contiene del orden de 90 subpaquetes, y `-base` unos 40. La aplicación usa
siete de `-good` y tres de `-base`.

**Verificación de que las dependencias finas no arrastran la familia.** Se
comprobó con `oe-pkgdata-util` que los `RDEPENDS` de los subpaquetes declarados
son solo bibliotecas:

    gstreamer1.0-plugins-base-app:               gstreamer1.0, libgstapp-1.0
    gstreamer1.0-plugins-base-videoconvertscale: glib-2.0, glibc,
                                                 gstreamer1.0, libgstvideo-1.0

Ninguno depende de `-meta` ni del conjunto completo. El desglose fino es, por
lo tanto, efectivo.

### Hallazgo 3 — entran 38 paquetes de `plugins-base` con 3 declarados

Pese a lo anterior, la imagen contiene 38 subpaquetes de
`gstreamer1.0-plugins-base` cuando el packagegroup declara tres (`-app`,
`-videoconvertscale`, `-pango`). Entre los que sobran:

| Subpaquete | Para qué sirve | ¿Lo usa el sistema? |
|---|---|---|
| `-alsa`, `-audioconvert`, `-audiomixer`, `-audioresample`, `-audiotestsrc`, `-audiorate` | Audio | No. La placa tiene el audio deshabilitado (`dtparam=audio=off`) para liberar el PWM del buzzer |
| `-vorbis`, `-theora`, `-ogg` | Códecs de audio y video libres | No |
| `-opengl` | Aceleración gráfica | No. Dispositivo sin pantalla |
| `-ximagesink`, `-xvimagesink` | Salida a servidor X | No. No hay servidor gráfico |
| `-playback`, `-compositor`, `-subparse` | Reproducción y composición | No |

Dado que los `RDEPENDS` de los subpaquetes finos no los arrastran (hallazgo 2),
entran por otra vía. La causa más probable es la misma de P-20: **Poky activa
`opengl` en `DISTRO_FEATURES` por omisión**, lo que hace que `plugins-base` se
construya con soporte gráfico y que el metapaquete entre completo.

**Impacto.** A diferencia de los módulos del kernel, estos son bibliotecas en
espacio de usuario que se cargan en el proceso: un fallo en el decodificador de
Vorbis o en el cliente X es código ejecutándose con los privilegios del
servicio. En un dispositivo sin audio ni pantalla, no deberían estar.

**Por qué no se corrigió.** Quitar `opengl wayland x11` de `DISTRO_FEATURES`
invalida todas las firmas de sstate y obliga a una recompilación completa, de
varias horas. Con el cronograma de entrega, el riesgo superó al beneficio. Está
registrado como P-20 en la bitácora.

---

## 4. Separación entre imagen de entrega y de desarrollo

El ítem G2 del acta exige que la imagen entregada no lleve concesiones de
desarrollo. Se resolvió con dos recetas: `acceso-image` (entrega) y
`acceso-image-dev`, que hereda de la primera y agrega lo que no debe
entregarse.

**Diferencia medida, paquete por paquete** (11 entradas):

| Paquete | Para qué estaba |
|---|---|
| `gstreamer1.0-plugins-ugly-x264`, `-locale-en-gb` | `x264enc`, término de comparación por software del ítem C2 |
| `libx264-165` | Biblioteca de x264 |
| `gstreamer1.0-tracers` | `libgstcoretracers.so`: el tracer de latencia del ítem D1 |
| `v4l-utils`, `libv4l`, `media-ctl` | `v4l2-ctl` para inspeccionar el codificador por hardware |
| `raspi-utils`, `dtc` | `vcgencmd` para la temperatura y el *throttling* (F4) |
| `sysstat` | `iostat` (F5) |
| `packagegroup-acceso-diagnostico` | El agrupador |

| | Entrega | Desarrollo |
|---|---|---|
| Paquetes totales | 2 255 | 2 266 |
| Espacio de usuario | **390** | 401 |
| Paquetes de GStreamer | **47** | 50 |
| Tamaño comprimido | **161 MB** | 163 MB |

Además, la imagen de entrega **no lleva** `allow-empty-password`,
`allow-root-login` ni `empty-root-password`, que sí están en la de desarrollo.
Esas tres features dejan la cuenta de root accesible sin credencial: son la
diferencia de seguridad más relevante entre ambas, aunque no aparezca en el
conteo de paquetes.

### Hallazgo 4 — declarar el conjunto completo para obtener un plugin

El análisis de esta diferencia expuso un defecto propio: para disponer de
`x264enc` se había declarado `gstreamer1.0-plugins-ugly` completo, lo que
arrastraba los decodificadores de ASF, DVD y RealMedia —formatos que el sistema
no procesa— a la imagen de desarrollo.

El subpaquete `gstreamer1.0-plugins-ugly-x264` no existía al momento de
declararlo porque el `PACKAGECONFIG[x264]` todavía no estaba habilitado; una vez
habilitado, el subpaquete se genera. Corregido declarando el subpaquete
específico.

Es el mismo error que el packagegroup fino busca evitar, cometido en el
subpaquete de diagnóstico.

**Efecto medido de la corrección.** Tras declarar
`gstreamer1.0-plugins-ugly-x264` en vez del conjunto completo y reconstruir:

| | Antes | Después |
|---|---|---|
| Subpaquetes de `plugins-ugly` en la imagen de desarrollo | 8 | **2** |
| Espacio de usuario (desarrollo) | 397 | **394** |
| Espacio de usuario (entrega) | 384 | 384 — sin cambio, como corresponde |

Los dos que quedan son `-x264`, que es el que se necesita, y
`-locale-en-gb`, su archivo de idioma. Desaparecieron los decodificadores de
ASF, DVD, DVD-LPCM y RealMedia, y el metapaquete.

---

### Hallazgo 5 — los tracers hubo que separarlos a mano

Habilitar `coretracers` para poder medir la latencia (ítem D1) deja
`libgstcoretracers.so` dentro del paquete `gstreamer1.0`, que la imagen de
entrega necesita: el tracer habría viajado en las dos. Se partió el paquete
desde un `.bbappend` con `PACKAGES =+ "${PN}-tracers"`, y se declaró en
`packagegroup-acceso-diagnostico`, para que entre solo en la de desarrollo.

Los *hooks* del tracer, en cambio, quedan compilados dentro de `libgstreamer`
en **ambas** imágenes. La asimetría es deliberada: así la biblioteca es la
misma en las dos, y la latencia medida sobre la imagen de desarrollo describe
también a la de entrega. Con `GST_TRACERS` sin definir —que es el caso del
servicio— el costo de los hooks es una comprobación por evento.

Es el mismo desglose fino del hallazgo 2, aplicado esta vez a una receta de
oe-core y no a un packagegroup propio.

---

## 5. Licencias

El build genera el manifiesto de licencias junto con el SBOM. Dos casos
requirieron aceptación explícita mediante `LICENSE_FLAGS_ACCEPTED`:

| Componente | Marca | Motivo de la aceptación |
|---|---|---|
| `linux-firmware-rpidistro-bcm43456` | `synaptics-killswitch` | Firmware WiFi que `core-image-base` arrastra por diseño del BSP |
| `x264` | `commercial` | Codificador GPL, usado solo como término de comparación en la imagen de desarrollo |

**x264 no está en la imagen de entrega.** Esto es relevante más allá de lo
técnico: x264 está bajo GPL y su distribución impone obligaciones que la imagen
de entrega, al no incluirlo, no asume.

Se detectó además un comportamiento que vale documentar: **sin
`LICENSE_FLAGS_ACCEPTED`, el `PACKAGECONFIG` correspondiente se ignora en
silencio.** No hay error ni advertencia; el plugin simplemente no se construye y
el fallo aparece después, como `Nothing RPROVIDES`.

---

## 6. Conclusiones

1. **El inventario de 2 255 paquetes está dominado por `kernel-modules`
   (83 %).** La superficie de ataque real en espacio de usuario es de 390
   paquetes. Reemplazar `kernel-modules` por la lista explícita de módulos
   necesarios es la mejora pendiente de mayor impacto.

2. **El desglose a subpaquetes finos funciona y es verificable.** Los
   `RDEPENDS` de los subpaquetes declarados no arrastran la familia completa.

3. **`DISTRO_FEATURES` por omisión anula parte de ese trabajo.** Treinta y ocho
   subpaquetes de `plugins-base` entran por `opengl`, incluyendo audio y salida
   a X11 en un dispositivo que no tiene ninguna de las dos cosas.

4. **La separación entre imagen de entrega y de desarrollo es efectiva y
   medible:** 11 paquetes de diferencia, todos identificados, más las tres
   features de acceso sin credencial.

5. **El análisis expuso un defecto propio** (hallazgo 4), que es el argumento
   más directo a favor de hacer este ejercicio: declarar un conjunto completo
   para obtener un solo plugin es exactamente lo que el desglose fino busca
   evitar.

---

## 7. Pendiente

- Completar el cruce automático contra la base de CVE. El mecanismo está
  habilitado; falta que la descarga del índice del NIST complete.
- Verificar en la placa con `lsmod` qué módulos se cargan realmente, y
  sustituir `kernel-modules` por esa lista.
- Quitar `opengl wayland x11` de `DISTRO_FEATURES` y medir la reducción (P-20).
