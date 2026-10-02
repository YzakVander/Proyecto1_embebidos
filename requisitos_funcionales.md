# Especificación de Requerimientos Funcionales - Proyecto 1: Sistema de Control de Acceso
**Curso:** Taller de Sistemas Embebidos (EL-5841)  
**Estándar usado como Referencia:** ISO/IEC/IEEE 29148:2018 

---

## Requisitos Funcionales

### **Requisito funcional 1: Transmisión de video en tiempo real**

* **Enunciado:** Durante la operación normal, el sistema deberá transmitir un flujo de video comprimido por red mediante el protocolo RTP/UDP hacia la dirección IP del puesto de vigilancia a una tasa mínima de 15 FPS.
* **Trazabilidad:** Caso de uso 1.
* **Método de Verificación:** Medición cuantitativa de tasa de cuadros en computadora remota.

---

### **Requisito funcional 2: Bifurcación y extracción de video en disco**

* **Enunciado:** El sistema deberá duplicar internamente el flujo de video capturado desde la cámara para guardar una copia en el disco local de la Raspberry Pi 4 en formato MP4 y permitir su extracción posterior.
* **Trazabilidad:** Caso de uso 2.
* **Método de Verificación:** Verificación de la creación, reproducibilidad y transferencia del archivo de video almacenado en la Raspberry Pi 4.

---

### **Requisito funcional 3: Captura de evento de identificación**

* **Enunciado:** La aplicación en Python en la Raspberry Pi 4 deberá detectar la recepción de cada comando del puesto de vigilancia (inicio de solicitud, permitir o denegar), enviado por la red desde la computadora remota, en un tiempo máximo de 100 ms desde su envío.
* **Trazabilidad:** Caso de uso 3.
* **Método de Verificación:** Medición del tiempo de ida y vuelta (RTT) entre el envío del comando y la confirmación de la Raspberry Pi 4. Un RTT ≤ 100 ms acota el tiempo de detección.

---

### **Requisito funcional 4: Registro de eventos en bitácora local**

* **Enunciado:** Al procesar un evento, la aplicación deberá registrar en un archivo de bitácora local en el almacenamiento de la Raspberry Pi 4 la fecha y hora exacta (timestamp) del instante de la decisión, en formato ISO-8601, junto con el resultado de la solicitud (permitido, denegado o denegado por vencimiento).
* **Trazabilidad:** Caso de uso 3, Caso de uso 10.
* **Método de Verificación:** Inspección del contenido del archivo `accesos.log` generado en la Raspberry Pi 4.

---

### **Requisito funcional 5: Indicación acústica del resultado**

* **Enunciado:** Al procesarse una solicitud de ingreso, el sistema deberá emitir por un buzzer pasivo conectado a la Raspberry Pi 4 un tono distinto para acceso permitido y para acceso denegado, con frecuencias y duraciones configurables, retornando posteriormente al silencio, y mostrar el resultado en la consola de la Raspberry Pi 4.
* **Trazabilidad:** Caso de uso 4.
* **Método de Verificación:** Inspección auditiva y medición de la frecuencia y la duración de la señal en la línea GPIO 18 por medio de osciloscopio.

---

### **Requisito funcional 6: Denegación por vencimiento de tiempo**

* **Enunciado:** El sistema deberá resolver como denegado toda solicitud cuya decisión no se reciba dentro de un plazo máximo configurable, y notificarlo al puesto de vigilancia.
* **Trazabilidad:** Caso de uso 5.
* **Método de Verificación:** Prueba temporizada (esperar expiración del plazo y verificar estado denegado).

---

### **Requisito funcional 7: Retención de evidencia por umbral**

* **Enunciado:** El sistema deberá mantener cada carpeta de evidencia (`evidencia/` y `eventos/`) por debajo de su propio tope configurable en megabytes, eliminando primero sus archivos más antiguos sin borrar el segmento en curso, y al iniciar deberá eliminar los archivos MP4 corruptos (sin índice) de ambas carpetas.
* **Trazabilidad:** Caso de uso 8.
* **Método de Verificación:** Prueba con topes reducidos en `acceso.conf` (pocos MB): verificar en la bitácora del servicio que cada carpeta se mantiene bajo su tope y que se borran los archivos más antiguos. Para los corruptos, truncar un MP4 copiado en la carpeta, reiniciar el servicio y verificar que se elimina.

---

### **Requisito funcional 8: Persistencia del registro de eventos**

* **Enunciado:** El registro de eventos (`accesos.log`) deberá persistir entre reinicios del sistema.
* **Trazabilidad:** Caso de uso 10.
* **Método de Verificación:** Prueba de reinicio del sistema operativo y validación de existencia e integridad del archivo de bitácora.

---

### **Requisito funcional 9: Estado de actuadores desde el arranque**

* **Enunciado:** La línea GPIO del actuador (GPIO 18, buzzer) deberá tener un estado definido (nivel bajo, en silencio) desde el arranque del kernel, antes de que inicie la aplicación en Python.
* **Trazabilidad:** Caso de uso 7.
* **Método de Verificación:** Inspección del estado del pin con `pinctrl get 18` y medición eléctrica inmediatamente después de energizar la placa.

---

### **Requisito funcional 10: Reinicio automático del servicio**

* **Enunciado:** El servicio deberá reiniciarse automáticamente ante una terminación anormal.
* **Trazabilidad:** Caso de uso 6.
* **Método de Verificación:** Prueba de terminación forzada del proceso (`kill`) y verificación de que el administrador de servicios lo levante de nuevo.

---

### **Requisito funcional 11: Cierre ordenado de video**

* **Enunciado:** Al detenerse, el sistema deberá cerrar ordenadamente el archivo de video en curso de modo que resulte reproducible.
* **Trazabilidad:** Caso de uso 9.
* **Método de Verificación:** Prueba de detención del servicio y validación de la integridad del último archivo `.mp4` (ej. usando `ffprobe`).

---

### **Requisito funcional 12: Lectura de credenciales QR**

* **Enunciado:** La aplicación deberá detectar y decodificar el identificador de una credencial QR presentada ante la cámara, analizando el video en vivo a una tasa configurable (5 análisis por segundo por defecto), sin reducir la tasa de transmisión exigida en el requisito funcional 1.
* **Trazabilidad:** Caso de uso 13.
* **Método de Verificación:** Presentar una credencial ocupando al menos el 25 % del alto de la imagen y medir en la bitácora del servicio el tiempo hasta su detección; verificar simultáneamente la tasa de cuadros en el puesto de vigilancia.

---

### **Requisito funcional 13: Resolución de acceso según el rol de la credencial**

* **Enunciado:** Al leer una credencial activa con rol de vigilante o mantenimiento, el sistema deberá otorgar el acceso sin intervención del vigilante; ante una credencial de visitante, desconocida o revocada, deberá abrir una solicitud que requiera la decisión del vigilante.
* **Trazabilidad:** Caso de uso 13, Caso de uso 12.
* **Método de Verificación:** Prueba con una credencial de cada tipo (mantenimiento, visitante, revocada y no registrada) y verificación del resultado en la bitácora de accesos y en el puesto de vigilancia.

---

### **Requisito funcional 14: Gestión persistente de credenciales**

* **Enunciado:** El sistema deberá permitir registrar, revocar y listar credenciales desde el puesto de vigilancia por el canal de red, conservando las credenciales revocadas como registro histórico y persistiendo el registro entre reinicios.
* **Trazabilidad:** Caso de uso 11, Caso de uso 12.
* **Método de Verificación:** Ejecutar los comandos de alta, baja y listado; reiniciar el sistema operativo y verificar que el registro (`credenciales.json`) conserva todas las credenciales con su estado.

---

## Requisitos No Funcionales

### **Requisito no funcional 1: Presupuesto de latencia**

* **Enunciado:** La latencia extremo a extremo deberá mantenerse dentro de un presupuesto escrito por etapa, verificado por medición independiente.
* **Trazabilidad:** Arquitectura de video.
* **Método de Verificación:** Medición de latencia desde la captura hasta la visualización con reloj o marca de tiempo.

---

### **Requisito no funcional 2: Intervalo de keyframes**

* **Enunciado:** El codificador deberá generar un cuadro clave al menos cada 1 s, de modo que el puesto de vigilancia pueda mostrar imagen en un máximo de 1 s al conectarse al stream o tras una pérdida de paquetes.
* **Trazabilidad:** Arquitectura de video.
* **Método de Verificación:** Inspección del parámetro `h264_i_frame_period` en la configuración y medición del intervalo entre cuadros clave en un video grabado (por ejemplo, con `ffprobe`).

---

### **Requisito no funcional 3: Estabilidad y uso de recursos**

* **Enunciado:** El sistema deberá operar de forma continua por un periodo de $\ge 4$ h sin crecimiento sostenido de memoria RAM (RSS) ni aumento indefinido de descriptores de archivo.
* **Trazabilidad:** Confiabilidad del sistema.
* **Método de Verificación:** Prueba de esfuerzo mediante ejecución continua y monitoreo de recursos del sistema.

---

### **Requisito no funcional 4: Desacople de hilos de ejecución**

* **Enunciado:** La decisión de acceso y el manejo de eventos de entrada deberán ejecutarse fuera del hilo de streaming de GStreamer.
* **Trazabilidad:** Diseño de software.
* **Método de Verificación:** Inspección del código fuente para asegurar la separación de hilos o procesos.

---

### **Requisito no funcional 5: Reconstrucción desde cero**

* **Enunciado:** La imagen del sistema (Yocto) deberá reconstruirse desde cero en una máquina limpia siguiendo únicamente el documento de instalación entregado.
* **Trazabilidad:** Portabilidad y documentación.
* **Método de Verificación:** Prueba de ejecución de la guía de instalación en un entorno virgen independiente.
