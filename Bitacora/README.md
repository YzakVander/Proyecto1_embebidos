# Bitácora individual de trabajo

**Estudiante:** Daniel Chavarría García
**Rol en el equipo:** B — Plataforma (Yocto, BSP, imagen) · asumiendo temporalmente el Rol A (aplicación)
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
| **D-08** | **09-19** | **`appsink` con búfer circular de pre-evento** | `split-now` sobre `splitmuxsink`; cuadro único | El clip necesita contexto ANTES del evento: una cámara de vigilancia real hace pre-roll. `split-now` empezaría el clip *en* el evento |
| **D-09** | **09-19** | **Guardar cuadros H.264 comprimidos, no crudos** | Cuadros I420 en RAM | 10 s comprimidos = 235 KiB medidos, contra ~415 MB crudos. Precio: hay que recortar en cuadro clave |
| **D-10** | **09-19** | **Ventana del clip: 5 s antes + 5 s después** | 3+2 | Más contexto para auditar. Con cuadros comprimidos el costo en RAM es irrelevante |
| **D-11** | **09-19** | **E3: reconectar con alerta, no morir** | Morir y que systemd reinicie | Decisión propia; el checklist acepta ambas pero exige decidir. Reintentos indefinidos cada 5 s |
| **D-12** | **09-19** | **H2: plazo de 30 s, vencimiento DEFINITIVO** | 5 s, 10 s | 30 s da margen a una persona real (latencias medidas: 6.8 s y 15.9 s). El vencimiento cierra la solicitud: un PERMITIR tardío se rechaza |
| **D-13** | **09-19** | **H6: archivo JSONL con `fsync`** | journald | H6 exige verificar persistencia tras reinicio; un archivo se inspecciona con `cat`. `fsync` lo protege de corte de energía, no solo de cierre ordenado |
| **D-14** | **09-19** | **B4/B5 se CUMPLEN, no se declaran N/A** | Declararlos no aplicables | Con `appsink` real hay topes de memoria y callback medible. Único N/A legítimo: **H4** (no hay cerradura física, solo LED indicadores) |

---

## Registro de tiempos de compilación

| Fecha | Objetivo | Inicio | Fin | Duración | Notas |
|---|---|---|---|---|---|
| 09-10 | `core-image-base` | 11:09 | 23:17 | ~6 h efectivas | 5819 tareas. Sstate previo solo aportó 5%: era de `qemux86-64` |
| 09-10 | `packagegroup-acceso` (dry-run) | — | — | ~2 min | 72% completo; ~1024 tareas nuevas pendientes |

---

## Registro de problemas y soluciones

| # | Fecha | Síntoma | Causa raíz | Solución | Tiempo |
|---|---|---|---|---|---|
| P-01 | 09-10 | `bitbake -e` sin salida, código 127 | Terminal nueva sin `oe-init-build-env`; 127 = comando no encontrado | Re-ejecutar el `source` | ~10 min |
| P-02 | 09-10 | Fallo de parseo de `local.conf` | Comilla sin abrir en `SSTATE_DIR` y typo `sysyemd` | `sed` + verificación con `bitbake -e` | ~15 min |
| P-03 | 09-10 | `Nothing RPROVIDES 'linux-firmware-rpidistro-bcm43456'` | Licencia restringida bloqueada por defecto | `LICENSE_FLAGS_ACCEPTED` | ~5 min |
| P-04 | 09-10 | Sstate compartido sin reutilización | `BB_HASHSERVE_DB_DIR` dentro del build | Apuntarlo a `${SSTATE_DIR}` | Detectado con `--dry-run` |
| P-05 | 09-10 | Windows congelado; `pgrep -c bitbake` = 0 | Falso negativo: BitBake corre como `python3`. El congelamiento fue presión de memoria del anfitrión | `pgrep -af`, `uptime` (load 7.2), fecha de los `log.do_*` | ~15 min |
| P-06 | 09-10 | `Nothing RPROVIDES 'gstremaer1.0-tools'` | Typo en `RDEPENDS` | `sed` | ~2 min |
| P-07 | 09-10 | Mismo error tras corregir el typo | La receta `gstreamer1.0-tools` **no existe** en 1.28.2; las herramientas vienen en el paquete base | Eliminar la línea | ~10 min |
| **P-08** | **09-19** | **`videotestsrc` negociaba `Y444_10LE` y `x264enc` producía perfil `high-4:4:4`** | El `capsfilter` fijaba resolución y tasa pero **no el formato de píxel**; GStreamer tomó el primero compatible, que era el más rico | Añadir `format=I420`. Perfil pasó a `high` (4:2:0) | ~20 min |
| **P-09** | **09-19** | **`fpsdisplaysink` e `identity silent=false` no imprimían nada** | En GStreamer 1.24 dejaron de escribir a stdout; publican por señal o por el log de depuración | Cambiar de instrumento: medir **tiempo total** de procesar N cuadros | ~30 min |
| **P-10** | **09-19** | **H2: un `PERMITIR` tardío era aceptado tras el vencimiento** | `esperar()` devolvía VENCIDO pero **no cerraba** la solicitud | Al vencer se fija el resultado y se marca el `Event` bajo lock. Verificado con 200 iteraciones de carrera | **Error crítico** |
| **P-11** | **09-19** | **Clip de 10 s salía corto** | El búfer se dimensionaba solo con `segundos_antes` | Dimensionar con `antes + despues` | ~10 min |
| **P-12** | **09-19** | **`mp4mux`: "Buffer has no PTS"** | El clip es flujo elemental: no lleva marcas de tiempo, y `mp4mux` no las deriva | `ffmpeg -r 30 -i ... -c copy`. El `-r` **antes** del `-i`; sin él ffmpeg asume 25 fps | ~25 min |
| **P-13** | **09-19** | **El clip no era Annex B: empezaba en `00 00 00 02`** | `h264parse` entregaba formato `avc` (NAL con prefijo de longitud) | Diagnosticado con `xxd`. Ver P-14 | ~15 min |
| **P-14** | **09-19** | **Al añadir `capsfilter byte-stream`: `not-negotiated` en bucle** | **Un `tee` impone las mismas caps a TODAS sus ramas.** Un `capsfilter` filtra, no convierte | Segundo `h264parse` en la rama del `appsink` | ~20 min |
| **P-15** | **09-19** | **Push rechazado: "fetch first"** | La rama `Daniel` remota tenía commits de la bitácora hechos desde la web | `git pull --rebase origin Daniel` | ~10 min |

---

## Entradas diarias

### 2026-09-10 · ___ h — Plataforma: árbol de capas e imagen base

_(entrada previa sin cambios — ver historial del repositorio)_

---

### 2026-09-19 · ___ h — Aplicación: pipeline, búfer circular y decisión de acceso

**Objetivo de la sesión**

Avanzar el Rol A mientras el compañero no está disponible: diseñar y validar
la tubería GStreamer, implementar la aplicación en Python y cerrar con
evidencia medida los ítems del checklist que no requieren la RPi4.

**Actividades**

1. Análisis del checklist del profesor (44 ítems, secciones A–H) y mapeo a los roles.
2. Sección A completa: lectura de caps negociados, justificación del `capsfilter`, inventario del grafo real.
3. Sección B: demostración medida del efecto de `queue` en las ramas de un `tee`.
4. Sección C parcial: medición de CPU del codificador por software.
5. Sección D: medición de latencia con el tracer y corrección del presupuesto.
6. Diseño e implementación de la aplicación completa en Python (8 módulos).
7. Pruebas unitarias del búfer circular y de la lógica de decisión.
8. Ejecución real de los tres casos de uso con evidencia.
9. Inicialización del repositorio git y publicación en la rama `Daniel`.

**Comandos relevantes**

```bash
# A1/A2/A4 - leer los caps, no suponerlos
gst-launch-1.0 -v videotestsrc ! video/x-raw,format=I420,... ! x264enc ! fakesink \
  2>&1 | grep -A2 "caps = "

# A5/A6 - inventario del grafo REAL
DOT=$(ls grafos/*PLAYING_PAUSED*.dot | tail -1)
grep -oE "Gst[A-Za-z0-9]+\\\\n" "$DOT" | sort | uniq -c | sort -rn
grep -icE "videoconvert|videoscale|videorate" "$DOT"

# D1 - latencia medida, no estimada
GST_DEBUG="GST_TRACER:7" GST_TRACERS="latency" gst-launch-1.0 -q ... \
  2>&1 | grep latency

# P-13 - diagnóstico del encuadre del clip
head -c 16 eventos/*.h264 | xxd

# Ejecución y verificación
python3 -m acceso -c config/acceso.conf --dot grafos
echo "SOLICITUD ID-001" > /tmp/acceso-eventos
python3 -m acceso -c config/acceso.conf --ver-bitacora
```

**Resultados**

| Medición | Valor |
|---|---|
| Conversores insertados por GStreamer en el grafo | **0** (consecuencia de fijar `format=I420`) |
| `queue` por rama de `tee` | 6 `queue` para 2 `tee` |
| Bloqueo sin `queue` | **122 s** contra **38 s** para 150 cuadros (>3×) |
| CPU codificando por software (x86) | **174 %** = 1.74 núcleos a 720p30 |
| Latencia extremo a extremo (602 muestras) | **12–21 ms** |
| Memoria del búfer circular lleno | **235 KiB** (10 s comprimidos) |
| Clip verificado | **10.47 s**, 1280×720, 30 fps |
| Vencimiento H2 | **30000.6 ms** (desviación de 0.6 ms) |

Bitácora de accesos con los tres resultados distintos:

```
20:38:53  ID-001  permitido                  6801.8 ms
20:39:27  ID-002  denegado                  15910.9 ms
20:42:33  ID-003  denegado_por_vencimiento  30000.6 ms
```

**Aprendizajes**

- **Sub-restringir un `capsfilter` es tan peligroso como sobre-restringirlo.**
  Sin `format=I420` el codificador producía perfil `high-4:4:4`, que la
  mayoría de reproductores no decodifica y el codificador por hardware de la
  RPi 4 no acepta. El pipeline "funcionaba" y el error habría aparecido en la
  demostración.
- **Un `tee` impone las mismas caps a todas sus ramas.** Si una rama necesita
  otro formato, hace falta un elemento *conversor* en esa rama; un
  `capsfilter` solo filtra lo que ya existe.
- **El presupuesto de latencia falló por 35×** (estimado 605 ms, medido 17 ms).
  La causa: un `queue` solo aporta latencia cuando está **lleno**. La tabla
  del checklist describe el peor caso, no la operación normal. La profundidad
  acota la latencia máxima bajo carga, no la nominal.
- **Un flujo H.264 elemental no lleva marcas de tiempo.** `mp4mux` las exige y
  no las deriva; `ffmpeg` sí, con `-r` *antes* del `-i`. Sin ese parámetro
  asume 25 fps y el clip se reproduce más lento que la realidad.
- **En control de acceso, el estado por omisión es negar.** El error P-10 —un
  `PERMITIR` tardío aceptado tras el vencimiento— habría abierto la puerta
  después de que el sistema ya denegó. Lo reveló una prueba, no la lectura del
  código.
- Las herramientas de diagnóstico cambian entre versiones: `fpsdisplaysink` e
  `identity silent=false` dejaron de imprimir a stdout en 1.24. Conviene medir
  con instrumentos independientes del elemento bajo prueba.

**Estado del checklist: 21 de 44 con evidencia**

| Sección | Cerrados | Pendientes |
|---|---|---|
| A · Caps | A1, A2, A4, A5, A6 | A3 (contar cuadros) |
| B · Topología | B1, B2, B3, B4, B5 | B6 (coordinación de EOS) |
| C · Hardware | C3 · C2 parcial | C1, C2, C4 — **requieren RPi4** |
| D · Latencia | D1, D3, D4 | D2 (cronómetro filmado) |
| E · Errores | E1, E3, E4 | E2, E5, E6 |
| F · Estabilidad | — | F1–F6 (corrida larga / RPi4) |
| G · Yocto | — | G1–G5 (Rol B) |
| H · Acceso | H1, H2, H6 | H3, H5, H7 · **H4 = N/A justificado** |

**Pendientes inmediatos (entrega del lunes)**

- [ ] D2 — medición de latencia con cronómetro filmado (~15 min)
- [ ] E6 — unidad systemd con `Restart=on-failure`, probada con `kill -9`
- [ ] H7 — política de retención de imágenes (dos párrafos, exigido por el checklist)
- [ ] Redactar los casos de uso nuevos CU-5 a CU-10 en formato ISO 29148
- [ ] Hoja de limitaciones declaradas (los 5 ítems bloqueados por hardware)

**Pendientes de plataforma (Rol B)**

- [ ] `acceso-image.bb` con servidor SSH
- [ ] G1 — desglosar el packagegroup a subpaquetes
- [ ] G4 — reconstrucción limpia sin `sstate-cache`

**Hallazgo de diseño sin resolver**

Al apagarse, el servicio **no espera** a las solicitudes en curso. Una decisión
tomada segundos antes del cierre puede no llegar a la bitácora — observado con
ID-003 en la primera ronda. En producción sería un defecto menor pero real.
Material para la tercera pregunta de la defensa oral.

**Coordinación con el compañero**

- **Pendiente:** informar que se usará **cámara USB** (`v4l2src`, no `libcamerasrc`).
- **Pendiente:** entregar la lista de elementos GStreamer usados para afinar el packagegroup (G1).
- **Pendiente:** acordar la rama de integración (local es `master`, remoto usa `main`).
- **Avance:** la aplicación del Rol A está implementada y validada; queda por revisar y continuar cuando se reincorpore.

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
