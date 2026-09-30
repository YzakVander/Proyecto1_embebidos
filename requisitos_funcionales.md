# Especificación de Requerimientos - Proyecto 1: Sistema de Control de Acceso
**Curso:** Taller de Sistemas Embebidos (EL-5841)
**Estándar usado como Referencia:** ISO/IEC/IEEE 29148:2018

---

## Requisitos Funcionales

### **Requisito funcional 1: Transmisión de video en tiempo real**

* **Enunciado:** Durante la operación normal, el sistema deberá transmitir un flujo de video comprimido por red mediante el protocolo RTP/UDP hacia la dirección IP del puesto de vigilancia.
* **Trazabilidad:** Caso de uso 1.
* **Método de Verificación:** Recepción y visualización del flujo en una computadora remota distinta de la Raspberry Pi 4.

---

### **Requisito funcional 2: Bifurcación y retención de video en disco**

* **Enunciado:** El sistema deberá duplicar internamente el flujo de video comprimido para guardar una copia en el disco local de la Raspberry Pi 4 en formato MP4, en segmentos cerrados e independientes, y permitir su extracción posterior.
* **Trazabilidad:** Caso de uso 2.
* **Método de Verificación:** Verificación de la creación, reproducibilidad y transferencia del archivo de video almacenado.

---

### **Requisito funcional 3: Captura de evento de identificación**

* **Enunciado:** La aplicación deberá detectar la recepción de una solicitud de ingreso y de la resolución del vigilante, e iniciar el procesamiento correspondiente.
* **Trazabilidad:** Caso de uso 3.
* **Método de Verificación:** Medición del tiempo de respuesta mediante marcas de tiempo registradas por la aplicación.

---

### **Requisito funcional 4: Registro de eventos en bitácora local**

* **Enunciado:** Al procesar un evento, la aplicación deberá registrar en un archivo de bitácora local la fecha y hora en formato ISO-8601, el identificador de la solicitud, el resultado y la latencia de decisión.
* **Trazabilidad:** Casos de uso 3, 5 y 10.
* **Método de Verificación:** Inspección del contenido del archivo de bitácora generado en la Raspberry Pi 4.

---

### **Requisito funcional 5: Conmutación de indicadores de estado**

* **Enunciado:** Al resolverse una solicitud de ingreso, el sistema deberá activar la línea GPIO correspondiente al resultado durante un intervalo configurable, retornando posteriormente al estado de reposo de forma automática.
* **Trazabilidad:** Caso de uso 4.
* **Método de Verificación:** Inspección visual de los indicadores y medición del intervalo de activación.

---

### **Requisito funcional 6: Denegación por vencimiento de tiempo**

* **Enunciado:** El sistema deberá resolver como denegada toda solicitud cuya decisión no se reciba dentro de un plazo máximo configurable. La decisión por vencimiento deberá ser definitiva: una resolución posterior sobre la misma solicitud no deberá surtir efecto.
* **Trazabilidad:** Caso de uso 5.
* **Método de Verificación:** Prueba temporizada sin emitir respuesta, y prueba de resolución tardía verificando su rechazo.

---

### **Requisito funcional 7: Retención de evidencia por umbral**

* **Enunciado:** El sistema deberá mantener el almacenamiento de evidencia por debajo de un umbral configurable, eliminando los segmentos más antiguos.
* **Trazabilidad:** Caso de uso 8.
* **Método de Verificación:** Prueba de llenado intencional del almacenamiento y verificación de la liberación de espacio.

---

### **Requisito funcional 8: Persistencia del registro de eventos**

* **Enunciado:** El registro de eventos deberá persistir entre reinicios del sistema y ante cortes de energía.
* **Trazabilidad:** Caso de uso 10.
* **Método de Verificación:** Reinicio del sistema operativo y validación de la existencia e integridad de la bitácora.

---

### **Requisito funcional 9: Estado de actuadores desde el arranque**

* **Enunciado:** Las líneas GPIO de los indicadores deberán tener un estado seguro definido desde el arranque del núcleo, antes de que inicie la aplicación.
* **Trazabilidad:** Caso de uso 7.
* **Método de Verificación:** Consulta del estado de las líneas GPIO inmediatamente después de energizar la placa, antes de iniciar el servicio.

---

### **Requisito funcional 10: Reinicio automático del servicio**

* **Enunciado:** El servicio deberá reiniciarse automáticamente ante una terminación anormal, tras un intervalo configurable.
* **Trazabilidad:** Caso de uso 6.
* **Método de Verificación:** Terminación forzada del proceso y verificación de que el gestor de servicios lo levanta nuevamente.

---

### **Requisito funcional 11: Cierre ordenado de video**

* **Enunciado:** Al detenerse, el sistema deberá cerrar ordenadamente el archivo de video en curso de modo que resulte reproducible.
* **Trazabilidad:** Caso de uso 9.
* **Método de Verificación:** Detención del servicio y validación de la integridad del último archivo generado.

---

### **Requisito funcional 12: Reconexión ante falla de la fuente de video**

* **Enunciado:** Ante la pérdida de la fuente de video, el sistema deberá registrar una alerta y reintentar la reconstrucción de la tubería de forma periódica hasta restablecer la operación.
* **Trazabilidad:** Caso de uso 6.
* **Método de Verificación:** Desconexión física de la cámara durante la operación y verificación de la alerta y del restablecimiento al reconectarla.

---

### **Requisito funcional 13: Configurabilidad sin recompilación**

* **Enunciado:** Los parámetros de operación del sistema deberán ser configurables mediante un archivo de texto en el destino, sin requerir recompilación de la imagen.
* **Trazabilidad:** Casos de uso 1, 4, 5 y 8.
* **Método de Verificación:** Modificación del archivo de configuración en la Raspberry Pi 4 y verificación del cambio de comportamiento tras reiniciar el servicio.

---

## Requisitos No Funcionales

### **Requisito no funcional 1: Presupuesto de latencia**

* **Enunciado:** La latencia extremo a extremo deberá mantenerse dentro de un presupuesto escrito por etapa, verificado por medición independiente.
* **Trazabilidad:** Arquitectura de video.
* **Método de Verificación:** Medición de latencia desde la captura hasta la visualización con marca de tiempo o reloj filmado.

---

### **Requisito no funcional 2: Intervalo de cuadros clave**

* **Enunciado:** El intervalo de cuadros clave deberá declararse justificando la espera máxima del cliente que se conecta a la transmisión.
* **Trazabilidad:** Arquitectura de video, Caso de uso 1.
* **Método de Verificación:** Inspección de los parámetros del codificador y medición del tiempo hasta la primera imagen en el receptor.

---

### **Requisito no funcional 3: Estabilidad y uso de recursos**

* **Enunciado:** El sistema deberá operar de forma continua por un periodo de al menos 4 horas sin crecimiento sostenido de memoria residente ni aumento indefinido de descriptores de archivo.
* **Trazabilidad:** Confiabilidad del sistema.
* **Método de Verificación:** Ejecución continua con monitoreo periódico de recursos.

---

### **Requisito no funcional 4: Desacople de hilos de ejecución**

* **Enunciado:** La decisión de acceso y el manejo de eventos de entrada deberán ejecutarse fuera del hilo de streaming de GStreamer, de modo que la tubería nunca quede a la espera de una resolución.
* **Trazabilidad:** Diseño de software, Casos de uso 3 y 5.
* **Método de Verificación:** Inspección del código fuente y verificación de que la transmisión continúa mientras una solicitud está pendiente.

---

### **Requisito no funcional 5: Aprovechamiento del codificador por hardware**

* **Enunciado:** La compresión de video deberá realizarse mediante el codificador H.264 por hardware del sistema en chip, y no por software, dentro de los límites del bloque.
* **Trazabilidad:** Arquitectura de video, Caso de uso 1.
* **Método de Verificación:** Inspección del perfil del archivo generado y comparación del consumo de procesador entre ambas rutas.

---

### **Requisito no funcional 6: Compresión única del flujo**

* **Enunciado:** El video deberá comprimirse una sola vez y el flujo resultante deberá distribuirse a los distintos destinos, evitando codificaciones redundantes.
* **Trazabilidad:** Arquitectura de video, Casos de uso 1 y 2.
* **Método de Verificación:** Inspección del grafo de la tubería en ejecución.

---

### **Requisito no funcional 7: Selección explícita de dependencias**

* **Enumerado:** La imagen del sistema deberá declarar sus dependencias a nivel de subpaquete, incluyendo únicamente los componentes que la aplicación utiliza.
* **Trazabilidad:** Portabilidad, tamaño de la imagen.
* **Método de Verificación:** Inspección de las recetas y del manifiesto de paquetes de la imagen generada.

---

### **Requisito no funcional 8: Reconstrucción desde cero**

* **Enunciado:** La imagen del sistema deberá reconstruirse desde cero en una máquina limpia siguiendo únicamente el documento de instalación entregado.
* **Trazabilidad:** Portabilidad y documentación.
* **Método de Verificación:** Ejecución de la guía de instalación en un entorno independiente sin caché de compilación.
