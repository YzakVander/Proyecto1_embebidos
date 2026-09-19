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

* **Enunciado:** La aplicación en Python en la Raspberry deberá detectar la recepción de una señal de entrada (pulsación de tecla en consola) en un tiempo máximo de 100 ms desde su generación.
* **Trazabilidad:** Caso de uso 3.
* **Método de Verificación:** Medición del tiempo de respuesta mediante marcas de tiempo en la aplicación de Python.

---

### **Requisito funcional 4: Registro de eventos en bitácora local**

* **Enunciado:** Al procesar un evento, la aplicación deberá registrar en un archivo de bitácora local en el almacenamiento de la Raspberry Pi 4 la fecha y hora exacta (timestamp) en formato ISO-8601 junto con el resultado de la solicitud (permitido o denegado).
* **Trazabilidad:** Caso de uso 3, Caso de uso 10.
* **Método de Verificación:** Inspección del contenido del archivo de texto `.log` generado en la Raspberry Pi 4.

---

### **Requisito funcional 5: Conmutación de LEDS de estado**

* **Enunciado:** Al procesarse una solicitud de ingreso, el sistema deberá conmutar el estado de los LEDS en la Raspberry Pi 4 para indicar el resultado durante un intervalo configurable, retornando posteriormente al estado original.
* **Trazabilidad:** Caso de uso 4.
* **Método de Verificación:** Inspección visual de los LEDS y medición del tiempo de encendido por medio de osciloscopio.

---

### **Requisito funcional 6: Denegación por vencimiento de tiempo**

* **Enunciado:** El sistema deberá resolver como denegado toda solicitud cuya decisión no se reciba dentro de un plazo máximo configurable.
* **Trazabilidad:** Caso de uso 5.
* **Método de Verificación:** Prueba temporizada (esperar expiración del plazo y verificar estado denegado).

---

### **Requisito funcional 7: Retención de evidencia por umbral**

* **Enunciado:** El sistema deberá mantener el almacenamiento de evidencia por debajo de un umbral configurable, eliminando los segmentos más antiguos.
* **Trazabilidad:** Caso de uso 8.
* **Método de Verificación:** Prueba de llenado intencional (ej. con `fallocate`) y verificación de liberación de espacio.

---

### **Requisito funcional 8: Persistencia del registro de eventos**

* **Enunciado:** El registro de eventos (`access.log`) deberá persistir entre reinicios del sistema.
* **Trazabilidad:** Caso de uso 10.
* **Método de Verificación:** Prueba de reinicio del sistema operativo y validación de existencia e integridad del archivo de bitácora.

---

### **Requisito funcional 9: Estado de actuadores desde el arranque**

* **Enunciado:** Las líneas GPIO del actuador (LEDS) deberán tener un estado definido (seguro/apagado) desde el arranque del kernel, antes de que inicie la aplicación en Python.
* **Trazabilidad:** Caso de uso 7.
* **Método de Verificación:** Inspección visual y eléctrica de los pines GPIO inmediatamente después de energizar la placa.

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

## Requisitos No Funcionales

### **Requisito no funcional 1: Presupuesto de latencia**

* **Enunciado:** La latencia extremo a extremo deberá mantenerse dentro de un presupuesto escrito por etapa, verificado por medición independiente.
* **Trazabilidad:** Arquitectura de video.
* **Método de Verificación:** Medición de latencia desde la captura hasta la visualización con reloj o marca de tiempo.

---

### **Requisito no funcional 2: Intervalo de keyframes**

* **Enunciado:** El intervalo de keyframes deberá declararse justificando la espera máxima del cliente.
* **Trazabilidad:** Arquitectura de video.
* **Método de Verificación:** Inspección de los parámetros del pipeline de codificación de video en GStreamer.

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
