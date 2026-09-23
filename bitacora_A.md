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