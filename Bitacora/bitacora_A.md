# Bitácora individual de trabajo

**Estudiante:** Isaac Vanderlucht López  
**Rol en el equipo:** A — Aplicación y Multimedia (Python + GStreamer)  
**Proyecto 1 — Sistema de control de acceso con Yocto Project y GStreamer**  
**Taller de Sistemas Embebidos · TEC · II Semestre 2026**  
**Prof. Dr. Ing. Johan Carvajal Godínez**  

---

## Entorno de trabajo

| Elemento | Valor |
|---|---|
| Host / Entorno | Contenedor Ubuntu 22.04 LTS vía Distrobox sobre Arch Linux |
| RAM / CPU | 16 GiB / 12 núcleos |
| Versiones | Python 3.10.12 · GStreamer 1.20.3 |
| Workspace | Repositorio Git local (`/app/` y `/docs/`) |

---

## Registro de decisiones de diseño

| # | Fecha | Decisión | Justificación |
|---|---|---|---|
| D-01 | 2026-09-16 | Adaptación de ISO/IEC/IEEE 29148:2018 (Anexo C) | Enfocar el esfuerzo documental solo en Casos de Uso y Requisitos Funcionales (SyRS/SRS). |
| D-02 | 2026-09-16 | Trigger de ingreso por evento de consola | Simplifica dependencias externas para priorizar el desarrollo de las tuberías en GStreamer. |
| D-03 | 2026-09-16 | Salida de actuación simulada con LED / texto | Permite validar la lógica en Python antes de probar con el relevador físico en el laboratorio. |
| D-04 | 2026-09-30 | Buzzer pasivo en GPIO 18 (PWM de hardware) en lugar de LEDs | Tonos distintos para permitido/denegado, perceptibles por el sujeto sin mirar la placa. |
| D-05 | 2026-09-30 | Clips de evento en MP4 (`mp4mux`) en lugar de `.h264` crudo | El `.h264` crudo no abre en muchos reproductores; se deja como respaldo si el empaquetado falla. |
| D-06 | 2026-10-01 | Credenciales en BMP en lugar de PNG | OpenCV lo lee y escribe con su codec interno, sin depender de libpng en la imagen de Yocto. |
| D-07 | 2026-10-01 | Topes de retención separados para `evidencia/` y `eventos/` | Evita que la grabación continua desplace los clips de evento y que la microSD se llene. |
| D-08 | 2026-10-04 | Validar el tutorial de Yocto en un contenedor Ubuntu 26.04.1 limpio hasta `bitbake -n`, sin la compilación completa | La simulación detecta en minutos los errores de configuración (paquetes, capas, variables); la compilación completa toma horas y queda para G4. |
| D-09 | 2026-10-08 | Medir la latencia de extremo a extremo (D2) filmando un cronómetro con milisegundos y comparándolo con el video recibido | Es independiente del tracer de GStreamer e incluye cámara, red y receptor; una captura de pantalla congela ambos valores en el mismo instante. |

---

## Registro de problemas y soluciones

| # | Fecha | Síntoma | Causa raíz | Solución |
|---|---|---|---|---|
| P-01 | 2026-09-16 | Duda sobre rol de la cámara en el evento | Creer que la cámara debía procesar la imagen/IA | Se aclaró que la cámara solo transmite video continuo; el evento lo maneja Python por aparte. |
| P-02 | 2026-09-16 | Términos ambiguos en requisitos ("sin retraso") | Redacción subjetiva no permitida por el estándar | Se agregaron condiciones cuantitativas medibles. |
| P-03 | 2026-09-30 | `ESTADO` seguía reportando la solicitud como pendiente tras decidir | La solicitud se liberaba al terminar el clip (~5 s después), no al decidir | Se libera en el instante de la decisión y la bitácora registra esa hora exacta. |
| P-04 | 2026-09-30 | Video atascado al aclarar la imagen | El elemento `gamma` en software saturaba un núcleo | Se descartó `gamma`; se fijaron los controles de la cámara en `extra-controls` (`exposure_time_absolute=2000`). |
| P-05 | 2026-10-02 | Clips corruptos al interrumpir la aplicación durante una solicitud | El apagado no esperaba a que terminara la escritura del clip | Contador de clips en curso; el apagado espera a que lleguen a cero (B6). |
| P-06 | 2026-10-04 | `RPI_EXTRA_CONFIG` definido en `acceso-image.bb` sin efecto | La variable la consume la receta `rpi-config`, que solo ve la configuración global, no la receta de la imagen | El valor efectivo es el de `local.conf`; verificado con `bitbake -e rpi-config` y documentado en el tutorial. |
| P-07 | 2026-10-08 | `analizar-dot.py` no separaba tipo y nombre de los elementos en el grafo volcado en la placa | Las etiquetas del `.dot` de GStreamer 1.28.5 traen saltos de línea reales, no la secuencia `\n` escrita | Se separa la etiqueta por ambas formas con `re.split`. |

---

## Entradas diarias

### 2026-09-16 · 4 h

**Objetivo de la sesión:** Definir los Casos de Uso del sistema y especificar los Requerimientos Funcionales de la aplicación bajo la norma ISO/IEC/IEEE 29148:2018.

**Actividades:**
1. Lectura del enunciado y acuerdo de responsabilidades con el Rol B.
2. Definición y redacción de los 4 Casos de Uso del sistema (CU-01 a CU-04).
3. Especificación formal de los 5 Requerimientos Funcionales (RF-01 a RF-05) con metadatos y métodos de verificación.

**Comandos relevantes:**
```bash
git status
```

### 2026-09-19 · 2 h

**Objetivo de la sesión:** Revisar los casos de uso y requisitos funcionales.

**Actividades:**
1. CU-2 pasa de grabación continua a extracción y consulta de evidencia por parte de mantenimiento.
2. CU-3 y CU-4 reescritos: el vigilante decide con una tecla y el sujeto percibe el resultado en los LEDs.
3. Ajustes de redacción en los RF.

### 2026-09-22 · 3 h

**Objetivo de la sesión:** Transmitir video entre dos computadoras y documentar el código base.

**Actividades:**
1. Configuración de `[streaming]` con la IP de la laptop receptora y pruebas con `videotestsrc` en la red de la casa.
2. Comentarios en `config.py` (dataclasses, `field`, `cargar()`) y en `pipeline.py`.

### 2026-09-23 · 2 h

**Objetivo de la sesión:** Adaptar la configuración a la Raspberry Pi 4.

**Actividades:**
1. `acceso.conf`: cámara USB (`v4l2src` + `jpegdec`) y codificador por hardware `v4l2h264enc` a 2.5 Mbit/s, GOP de 30.
2. Avance en la documentación de `pipeline.py` y commit previo al merge con `main`.

### 2026-09-24 · 2 h

**Objetivo de la sesión:** Documentar el flujo principal de la aplicación.

**Actividades:**
1. Comentarios en `servicio.py`, `__main__.py` y `pipeline.py`.

### 2026-09-30 · 2 h

**Objetivo de la sesión:** Comparar los casos de uso y requisitos con el estado actual del proyecto para identificar lo que falta desarrollar, y actualizar la documentación.

**Actividades:**
1. Trazabilidad de cada CU y RF contra los módulos de `app/acceso/` y `config/acceso.conf`.
2. Faltantes identificados: el vigilante (en otra computadora) no tenía forma de enviar su decisión a la placa; retención de evidencia (RF-7) sin implementar; la bitácora se escribía ~5 s después de la decisión; reinicio automático con systemd (RF-10) pendiente del Rol B.
3. Definición del flujo de interacción con el Rol B: el vigilante abre la solicitud enviando un mensaje a la placa, la cuenta regresiva corre en la placa y luego el vigilante envía la decisión.
4. Actualización de `casos_uso.md` (CU-2, 3, 4, 5, 7, 10) y `requisitos_funcionales.md` (RF-3, 4, 5, 6, 8, 9 y RNF-2) para reflejar el canal de red, el buzzer, los clips MP4 y la bitácora `accesos.log`.

**Pendientes:** retención de evidencia (RF-7), script de extracción de videos por SSH (CU-2), programa del puesto de vigilancia, reinicio automático con systemd (Rol B).

### 2026-09-30 · 10 h

**Objetivo de la sesión:** Implementar el mecanismo de interacción entre la placa y la computadora del puesto de vigilancia, ajustar la configuración de la cámara y mejorar la generación de evidencias.

**Actividades:**
1. Canal TCP en la placa (`red.py`, puerto 5001) con los comandos `SOLICITUD`, `PERMITIR`, `DENEGAR`, `ESTADO` y `PING`. Cada comando recibe `OK`/`ERROR` y la placa avisa al vigilante con mensajes `EVENTO` (apertura, resultado y vencimiento). Identificador de solicitud generado con fecha y hora (`S-AAAAMMDD-HHMMSS`).
2. Reemplazo de los LEDs por un buzzer pasivo en GPIO 18 con PWM de hardware: tono agudo para permitido y tres pitidos graves para denegado, más un mensaje destacado en la consola. Script `probar-buzzer.sh` para probarlo sin la aplicación.
3. Preparación de la Raspberry Pi 4 con Raspberry Pi OS: dependencias de GStreamer, PWM habilitado en `config.txt`, acceso por SSH, clonación del repositorio y llave SSH para GitHub.
4. Pruebas en la placa: video recibido en la laptop y solicitudes resueltas desde la laptop con `nc`.
5. Corrección: tras decidir, `ESTADO` seguía reportando la solicitud como pendiente. Ahora se libera en el instante de la decisión y la bitácora registra esa hora exacta.
6. Clips de evento guardados directamente en MP4 (`appsrc ! h264parse ! mp4mux`) en lugar de `.h264` crudo, que muchos reproductores no abren. Respaldo en `.h264` si el empaquetado falla.
7. Ajuste de cámara para 30 fps fijos: la exposición automática bajaba a ~25 fps y la manual con valores bajos daba imagen oscura. Se descartó el elemento `gamma` en software porque saturaba un núcleo y atascaba el video. Se fijaron todos los controles en `extra-controls`, con `exposure_time_absolute=2000`.

**Resultados:** 30 fps con imagen clara; clips MP4 de ~10 s reproducibles; la corrección de la solicitud pendiente pasó 50 ciclos seguidos sin fallos.

**Pendientes:** conectar y probar el buzzer físico.

**Comandos relevantes:**
```bash
sudo apt install python3-gi gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav v4l-utils tmux
pinctrl get 18
v4l2-ctl -d /dev/video0 --list-formats-ext
sudo python3 -m acceso -c config/acceso.conf
nc <ip-rpi> 5001
ffprobe -v error -show_entries stream=avg_frame_rate evidencia/evidencia_00000.mp4
```

### 2026-10-01 · 4 h

**Objetivo de la sesión:** Evitar que la evidencia llene la microSD y alinear la documentación con la lectura de QR.

**Actividades:**
1. Módulo `retencion.py`: tope por carpeta (`evidencia/` 500 MB, `eventos/` 150 MB), borrado de los archivos más viejos y eliminación de MP4 corruptos al arrancar.
2. Credenciales generadas en BMP en lugar de PNG para no depender de libpng en la imagen de Yocto.
3. Actualización de RF-7 y nuevos RF-12 a RF-14 (lectura de QR, resolución por rol, gestión de credenciales) en `requisitos_funcionales.md` y `casos_uso.md`.

### 2026-10-02 · 10 h

**Objetivo de la sesión:** Implementar el cliente del puesto de vigilancia y cerrar las justificaciones y correcciones del Rol A que no requieren la placa.

**Actividades:**
1. Cliente `vigilancia.py` y script `recolectar-evidencia.sh` (clips y log por SSH). Comandos nuevos `BORRAR`, `REGENERAR_QR` y `BORRAR_CREDENCIALES`.
2. Profundidad explícita en `queue_grabacion`, justificaciones A4/B2, y documentos H7 (`politica-de-retencion.md`) y H1 (`H1-arquitectura-hilos.md`, 9 hilos).
3. Correcciones E4 (EOS directo a la cola de grabación) y B6 (al detener se espera a los clips en curso para no dejarlos corruptos).
4. Medición A3: 29.70 fps con buena luz.
5. Instrumentación B5 (`Cronometro`) y C4 (la copia para el QR baja de 30 a ~8 por segundo).
6. Scripts de medición (`a6-grafo.sh`, `analizar-dot.py`, `d1-latencia.sh`, `analizar-segmentos.sh`, `g1-plugins.sh`), actualización del README y guion para la sesión en placa (`guion-placa-rol-a.md`).

**Pendientes:** sesión en placa según el guion.

### 2026-10-04 · 4 h

**Objetivo de la sesión:** Revisar el estado del proyecto contra la especificación y generar el tutorial de síntesis e instalación de la imagen Yocto.

**Actividades:**
1. Bitácora completada con las entradas faltantes (19/09 a 02/10) a partir de los commits, y con las tablas de decisiones y problemas.
2. Revisión del repositorio contra la especificación: faltaban el tutorial y la declaración de uso de IA, la copia de la app en la receta estaba desactualizada y había errores en la GUI del puesto de vigilancia. Se agregó a `.gitignore` la exclusión de las imágenes QR que traen los clientes.
3. Tutorial `docs/tutorial-imagen-yocto.html` con la configuración del Rol B. Se validó en un contenedor Ubuntu 26.04.1 limpio (distrobox) hasta la simulación completa: `bitbake -n acceso-image`, 7623 tareas sin errores.
4. Actualización de los documentos desactualizados (H1, guion de laboratorio, política de retención, D4, G5, README) y de la declaración de uso de IA (parte del Rol A).

**Resultados:** el tutorial queda validado hasta el paso previo a la compilación; el host, los paquetes, las capas y la configuración funcionan en una máquina limpia. Se detectó que `RPI_EXTRA_CONFIG` solo tiene efecto en `local.conf` y que el repositorio es público.

**Pendientes:** compilación completa desde cero (G4), sesión en la placa y etiqueta de entrega para el tutorial.

**Comandos relevantes:**
```bash
distrobox create --name yocto-limpio --image ubuntu:26.04 --home ~/distrobox/yocto-limpio
source layers/openembedded-core/oe-init-build-env build
bitbake -p
bitbake -n acceso-image
bitbake -e rpi-config | grep ^RPI_EXTRA_CONFIG=
```

### 2026-10-05 · 1.5 h

**Objetivo de la sesión:** Obtener el grafo GStreamer del receptor del puesto de vigilancia (equivalente a A6, del lado de la computadora que recibe el video).

**Actividades:**
1. Script `grafo-receptor.sh`: corre la misma tubería que abre `puesto-vigilancia.py` con `GST_DEBUG_DUMP_DOT_DIR` definido, la cierra con SIGINT para obtener el volcado `PLAYING_PAUSED` (el único con los caps ya negociados) y lo convierte a imagen con Graphviz.
2. Opción `-i`: el script abre el canal TCP 5001 con la placa durante la captura para que redirija el video a la computadora, sin necesidad de tener un cliente abierto. Opciones para puerto, duración, carpeta, formato (svg, png, pdf) y sink.

**Comandos relevantes:**
```bash
./app/scripts/grafo-receptor.sh -i <ip-rpi>
```

### 2026-10-08 · 6 h

**Objetivo de la sesión:** Obtener en la placa, con la imagen Yocto, el grafo real de la tubería y la medición de latencia de extremo a extremo.

**Actividades:**
1. Volcado del grafo de la aplicación en la Raspberry Pi 4 (GStreamer 1.28.5, `/etc/acceso/acceso.conf`) y análisis con `analizar-dot.py`: inventario de elementos (A5/A6), caps negociados en cada frontera (A1), entrada del codificador `v4l2h264enc` en DMABuf (A2), salidas de cada `tee` (B1) y profundidad de cada `queue` (B3). Resultado en `A1-A6-grafo-rpi4.txt`, junto con el `.dot` y el `.svg`.
2. Corrección de `analizar-dot.py`: el `.dot` de la placa trae saltos de línea reales en las etiquetas (P-07).
3. Medición D2 de latencia de extremo a extremo con un cronómetro filmado por la cámara (D-09): 5 capturas, mediana de 172 ms (mínimo 115, máximo 182). Comparación con el presupuesto D4 (170-220 ms): más de la mitad corresponde al `rtpjitterbuffer` de 100 ms del receptor.
4. `.gitignore`: se versionan como evidencia del acta los grafos `*-rpi4.dot`/`*-rpi4.svg` y las capturas de `app/mediciones/`.

**Resultados:** la ruta de video en la placa usa solo decodificadores, conversores y codificador por hardware (`v4l2jpegdec`, `v4l2convert`, `v4l2h264enc`); latencia medida dentro del presupuesto.

**Pendientes:** medición D1 con el tracer en la placa.

**Comandos relevantes:**
```bash
python3 app/scripts/analizar-dot.py app/grafos/acceso-rpi4.dot
dot -Tsvg app/grafos/acceso-rpi4.dot -o app/grafos/pipeline-acceso-rpi4.svg
python3 app/scripts/vigilancia.py
```
