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

---

## Registro de problemas y soluciones

| # | Fecha | Síntoma | Causa raíz | Solución |
|---|---|---|---|---|
| P-01 | 2026-09-16 | Duda sobre rol de la cámara en el evento | Creer que la cámara debía procesar la imagen/IA | Se aclaró que la cámara solo transmite video continuo; el evento lo maneja Python por aparte. |
| P-02 | 2026-09-16 | Términos ambiguos en requisitos ("sin retraso") | Redacción subjetiva no permitida por el estándar | Se agregaron condiciones cuantitativas medibles. |

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

### 2026-09-30 · 2 h

**Objetivo de la sesión:** Comparar los casos de uso y requisitos con el estado actual del proyecto para identificar lo que falta desarrollar, y actualizar la documentación.

**Actividades:**
1. Trazabilidad de cada CU y RF contra los módulos de `app/acceso/` y `config/acceso.conf`.
2. Faltantes identificados: el vigilante (en otra computadora) no tenía forma de enviar su decisión a la placa; retención de evidencia (RF-7) sin implementar; la bitácora se escribía ~5 s después de la decisión; reinicio automático con systemd (RF-10) pendiente del Rol B.
3. Definición del flujo de interacción con el Rol B: el vigilante abre la solicitud enviando un mensaje a la placa, la cuenta regresiva corre en la placa y luego el vigilante envía la decisión.
4. Actualización de `casos_uso.md` (CU-2, 3, 4, 5, 7, 10) y `requisitos_funcionales.md` (RF-3, 4, 5, 6, 8, 9 y RNF-2) para reflejar el canal de red, el buzzer, los clips MP4 y la bitácora `accesos.log`.

**Pendientes:** retención de evidencia (RF-7), script de extracción de videos por SSH (CU-2), programa del puesto de vigilancia, reinicio automático con systemd (Rol B).

### 2026-09-30 · 6 h

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
