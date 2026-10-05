# Declaración de uso de inteligencia artificial

**Proyecto 1 — Sistema operativo a la medida para un sistema de control de acceso
con Yocto Project y GStreamer**
Taller de Sistemas Embebidos · II Semestre 2026
Prof. Dr. Ing. Johan Carvajal Godínez

Autores:
- Daniel Chavarría García — Rol B (plataforma y Yocto)
- Isaac Vanderlucht López — Rol A (aplicación y multimedia)

Cada autor declara su propio uso, con la misma estructura y las mismas
categorías, para que los niveles se puedan comparar. La sección final de
verificación y responsabilidad es común a los dos.

---

## Parte 1 — Daniel Chavarría García (Rol B)

### 1.1 Modelo empleado

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

### 1.2 Nivel de uso por tipo de tarea

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

### 1.3 Para qué se usó

- Generar la estructura inicial de los módulos Python y de las recetas de Yocto.
- Proponer comandos de verificación y métodos de medición.
- Formular hipótesis durante la depuración de fallos en la Raspberry Pi 4.
- Interpretar mensajes de error de GStreamer, BitBake y el kernel.
- Redactar documentación técnica a partir de datos propios.
- Contrastar el estado del proyecto contra el acta de validación.

### 1.4 Para qué NO se usó

- **No se generaron datos de medición.** Todas las cifras del directorio
  `app/mediciones/` provienen de ejecuciones reales en la plataforma.
- **No se delegaron las decisiones de diseño.** La arquitectura del sistema,
  el reparto de roles y las decisiones de ingeniería son de los autores.
- **No se aceptó código sin verificar.** Todo lo generado se ejecutó y se
  corrigió contra el comportamiento observado.

### 1.5 Correcciones a la IA: dónde se equivocó

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

## Parte 2 — Isaac Vanderlucht López (Rol A)

### 2.1 Modelos empleados

Se utilizaron dos modelos en momentos distintos del proyecto: **Gemini** al
inicio y **Claude** durante la mayor parte del trabajo. La IA se usó a lo largo
de todo el proyecto.

| Dato | Valor |
|---|---|
| Proveedores | Google (al inicio) · Anthropic (la mayor parte del proyecto) |
| Modelos | Gemini 3.6 Flash · Claude Opus 5.5 |
| Interfaz | Gemini: navegador web · Claude: navegador web (claude.ai) y Claude Code (asistente en la terminal, trabajando sobre el repositorio local) |
| Periodo de uso | setiembre – octubre de 2026 |
| Sesiones de trabajo | _(completar)_ |

### 2.2 Nivel de uso por tipo de tarea

Mismo criterio que la Parte 1: se declara por categoría, porque un porcentaje
global sería engañoso.

| Tarea | Nivel de uso | Descripción |
|---|---|---|
| Casos de uso y requisitos | **Medio** | El contenido y los criterios medibles los definió el autor según la norma vista en el curso; la IA ayudó a redactarlos y a revisar su trazabilidad. |
| Código Python de la aplicación | **Alto** | Canal de red con el puesto de vigilancia, buzzer por PWM, retención de evidencia, comandos de credenciales y correcciones de cierre (E4, B6, C4). Generado con IA, probado en la placa y corregido según lo observado. |
| Scripts y clientes del puesto de vigilancia | **Alto** | `vigilancia.py`, `recolectar-evidencia.sh` y los scripts de medición. |
| Documentación del proceso con Yocto | **Alto** | Redacción del tutorial de síntesis e instalación a partir de la configuración del Rol B y de una validación propia en un entorno limpio. |
| Diagnóstico de fallos en hardware | **Medio** | Formulación de hipótesis (exposición de la cámara, solicitud que seguía pendiente, clips corruptos al interrumpir). Las pruebas se hicieron en la placa. |
| Redacción de documentación | **Alto** | Justificaciones de la tubería, arquitectura de hilos, política de retención, copias de memoria, guion de la defensa y bitácora, a partir de datos y hallazgos propios. |
| Mediciones y evidencia | **Bajo** | Las mediciones se ejecutaron en la plataforma real y en el entorno de validación. La IA propuso el método; los números son medidos, no generados. |
| Decisiones de diseño | **Bajo** | Las decisiones fueron del autor; ver 2.4. |
| Control de versiones e integración | **Nulo** | Se le prohibió a la IA toda operación de git. Ramas, commits, merges e integración con el Rol B los hizo el autor. |

### 2.3 Para qué se usó

- Generar e iterar el código de la aplicación y de los scripts.
- Revisar el estado del proyecto contra la especificación y el acta de
  validación, e identificar documentos desactualizados.
- Redactar documentación técnica y la bitácora a partir de los commits y de
  los datos propios.
- Preparar los pasos de verificación del tutorial y guiar su ejecución en un
  contenedor Ubuntu 26.04 limpio.
- Preparar el guion de la defensa oral a partir de la evidencia del repositorio.

### 2.4 Para qué NO se usó

- **No se generaron datos de medición.** Las cifras provienen de ejecuciones
  reales; la validación del tutorial la corrió el autor en su equipo.
- **No se delegaron las decisiones de diseño ni de proceso.** Decisiones del
  autor, entre otras:
  - **Del sistema:**
    - Adaptar ISO/IEC/IEEE 29148 (Anexo C) a casos de uso y requisitos.
    - Que el vigilante abra la solicitud desde su computadora y que el plazo
      corra en la placa.
    - Buzzer pasivo por PWM en lugar de LEDs.
    - Clips en MP4 con respaldo en `.h264`.
    - Exposición fija de la cámara, descartando la corrección `gamma` por
      software tras probar en vivo.
    - Credenciales en BMP.
    - Topes de retención separados por carpeta y borrado de MP4 corruptos al
      arrancar.
    - Borrado de evidencia por SSH y no por el canal de decisiones.
    - Confirmación obligatoria para borrar credenciales.
    - QR recolectados fuera del repositorio.
    - Bitácora de accesos sin tope.
  - **Del proceso:**
    - Trabajar siempre en la rama propia.
    - Exigir permiso antes de cualquier edición.
    - Asumir el tutorial del Rol B por el tiempo disponible.
    - Validarlo en un entorno limpio.
    - Entregarlo en HTML sin publicarlo fuera del repositorio.
    - Conservar como históricos los documentos obsoletos en lugar de borrarlos.
- **No se aceptaron cambios sin revisión.** Desde el 2026-10-02 la IA debe
  proponer cada cambio y esperar la aprobación del autor antes de editar
  cualquier archivo.

### 2.5 Correcciones a la IA: dónde se equivocó

Con el mismo criterio que la Parte 1: es la evidencia más directa del nivel de
supervisión.

**Trabajo sobre la rama equivocada.** En dos ocasiones la IA editó archivos
estando en `main` en lugar de la rama del autor. Lo detectó el autor y la
corrección del flujo (verificar la rama antes de editar) quedó como regla.

**Supuestos en lugar de preguntas.** Al preparar el tutorial de Yocto, la IA
empezó a redactarlo con supuestos sin confirmar sobre la configuración del
Rol B. El autor la detuvo y exigió que preguntara antes de asumir; las
preguntas resultantes se respondieron con el Rol B y cambiaron varios pasos
del tutorial.

**Versión equivocada de Yocto.** La IA escribió que la serie wrynose era la
5.1, tomando el dato de un archivo de mediciones sin verificarlo. Es la serie
6.0; se corrigió en el tutorial y en `G5-versiones-host.txt`.

**Afirmación sin verificar sobre el repositorio.** La IA dio por hecho que el
repositorio era privado. La validación en un entorno limpio mostró que se
clona sin credenciales, es decir, que es público.

**Horas de trabajo en la bitácora.** La IA estimó las horas de cada día a
partir de las horas de los commits. El autor corrigió tres días (24/09, 30/09
y 01/10) con las horas reales.

---

## Verificación y responsabilidad (común a los dos autores)

Todo el código generado con asistencia de IA fue ejecutado y verificado sobre
la plataforma real. Los autores comprenden el funcionamiento de cada módulo,
cada receta y cada decisión de configuración, y pueden explicarlos y
defenderlos.

La responsabilidad sobre el contenido entregado es enteramente de los autores.
