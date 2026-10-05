# Declaración de uso de inteligencia artificial

**Proyecto 1 — Sistema operativo a la medida para un sistema de control de acceso
con Yocto Project y GStreamer**
Taller de Sistemas Embebidos · II Semestre 2026
Prof. Dr. Ing. Johan Carvajal Godínez

Autor de esta declaración: Daniel Chavarría García — Rol B (plataforma y Yocto)

---

## 1. Modelo empleado

Se utilizó **Claude**, de Anthropic, a través de la interfaz web (claude.ai).
No se emplearon otros modelos ni asistentes de código (no se usó ChatGPT,
GitHub Copilot, Gemini ni herramientas equivalentes).

| Dato | Valor |
|---|---|
| Proveedor | Anthropic |
| Modelo | Claude — versión: _(verificar al pie de las respuestas en la interfaz)_ |
| Interfaz | claude.ai (web) |
| Periodo de uso | setiembre – octubre de 2026 |
| Sesiones de trabajo | 8 conversaciones sobre este proyecto |

---

## 2. Nivel de uso por tipo de tarea

El nivel varía mucho según la tarea, de modo que un porcentaje global sería
engañoso. Se declara por categoría:

| Tarea | Nivel de uso | Descripción |
|---|---|---|
| Código Python de la aplicación | **Alto** | Generación inicial de los módulos y refinamiento posterior. Revisado, probado y corregido por los autores. |
| Recetas y capa de Yocto | **Alto** | Estructura de `meta-acceso`, packagegroup, recetas de imagen y unidad systemd. |
| Diagnóstico de fallos en hardware | **Medio** | Formulación de hipótesis y comandos de verificación. Las conclusiones se validaron siempre contra mediciones en la placa. |
| Depuración de la tubería GStreamer | **Medio** | Interpretación de errores de negociación y de la salida del tracer. |
| Redacción de documentación | **Alto** | Estructura y redacción de documentos técnicos a partir de datos y hallazgos propios. |
| Mediciones y evidencia | **Bajo** | Las mediciones se ejecutaron en la plataforma real. La IA propuso el método; los números son medidos, no generados. |
| Decisiones de diseño | **Bajo** | Las decisiones de arquitectura se tomaron por los autores; en varios casos corrigiendo lo que la IA proponía. |

---

## 3. Para qué se usó

- Generar la estructura inicial de los módulos Python y de las recetas de Yocto.
- Proponer comandos de verificación y métodos de medición.
- Formular hipótesis durante la depuración de fallos en la Raspberry Pi 4.
- Interpretar mensajes de error de GStreamer, BitBake y el kernel.
- Redactar documentación técnica a partir de datos propios.
- Contrastar el estado del proyecto contra el acta de validación.

## 4. Para qué NO se usó

- **No se generaron datos de medición.** Todas las cifras del directorio
  `app/mediciones/` provienen de ejecuciones reales en la plataforma.
- **No se delegaron las decisiones de diseño.** La arquitectura del sistema,
  el reparto de roles y las decisiones de ingeniería son de los autores.
- **No se aceptó código sin verificar.** Todo lo generado se ejecutó y se
  corrigió contra el comportamiento observado.

---

## 5. Correcciones a la IA: dónde se equivocó

Esta sección se incluye porque es la evidencia más honesta del nivel real de
supervisión. En varias ocasiones la propuesta de la IA fue incorrecta y se
descartó por medición o por criterio propio.

**Hipótesis de diagnóstico descartadas.** Ante el error
`bcm2835_codec_start_streaming: Failed enabling i/p port, ret -3`, la IA
propuso sucesivamente memoria CMA insuficiente, reparto `gpu_mem` y modo de
E/S de los buffers. Las tres se descartaron por medición: CMA tenía 512 MiB
reservados con 507 libres, subir `gpu_mem` a 256 no cambió nada, y las tres
variantes de `io-mode` fallaron igual. La causa real resultó ser otra y se
documentó en `app/mediciones/C1-hallazgo-contextos.txt`.

**Diagnóstico equivocado del codificador.** A partir de esos fallos la IA
concluyó que el elemento `v4l2h264enc` estaba roto y recomendó migrar a
codificación por software. La verificación posterior mostró que el servicio
**sí estaba codificando por hardware correctamente** (segmentos MP4 válidos
de 17.4 MB/min). La recomendación se retiró y no se aplicó.

**Nombre de clase de Yocto, dos intentos fallidos.** Para habilitar el
análisis de vulnerabilidades, la IA propuso `INHERIT += "cve-check"` (clase
inexistente en wrynose) y luego `INHERIT += "sbom-cve-check"` (existe, pero
en `classes-recipe/`, que no se hereda desde `local.conf`). Ambos intentos
rompieron el parseo de BitBake y hubo que revertirlos. La forma correcta
resultó ser un fragmento de configuración.

**Decisiones de diseño corregidas por los autores.** Se mantuvo el buzzer
pasivo con PWM frente a la sugerencia de conservar LEDs; se exigió que la
revocación de credenciales fuera permanente sin posibilidad de reactivación,
por seguridad; y se rechazó versionar archivos `.bak` duplicados.

**Dependencias que la IA no detectó.** La desincronización entre
`app/acceso/` y la copia de la receta —que dejó fuera `retencion.py` y cinco
módulos desactualizados— se encontró por comparación sistemática iniciada por
el autor, no por sugerencia de la IA.

---

## 6. Verificación y responsabilidad

Todo el código generado con asistencia de IA fue ejecutado y verificado sobre
la plataforma real. Los autores comprenden el funcionamiento de cada módulo,
cada receta y cada decisión de configuración, y pueden explicarlos y
defenderlos.

La responsabilidad sobre el contenido entregado es enteramente de los autores.

---

_Fecha: _______________    Firma: _______________________________
