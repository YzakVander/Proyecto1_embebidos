# Especificación de Requerimientos Funcionales - Proyecto 1: Sistema de Control de Acceso
**Curso:** Taller de Sistemas Embebidos (EL-5841)[cite: 1]  
**Estándar usado como Referencia:** ISO/IEC/IEEE 29148:2018 
---

### **Requisito funcional 1: Transmisión de video en tiempo real**

* **Enunciado:** Durante la operación normal, el sistema deberá transmitir un flujo de video comprimido por red mediante el protocolo RTP/UDP hacia la dirección IP del puesto de vigilancia a una tasa mínima de 15 FPS.
* **Trazabilidad:** Caso de uso 1.
* **Método de Verificación:** Medición cuantitativa de tasa de cuadros en computadora remota.

---

### **Requisito funcional 2: Bifurcación y almacenamiento de video en disco**

* **Enunciado:** El sistema deberá duplicar internamente el flujo de video capturado desde la cámara para guardar una copia en el disco local de la Raspberry Pi 4 en formato MP4, de manera simultánea a la transmisión en red.
* **Trazabilidad:** Caso de uso 2.
* **Método de Verificación:** Verificación de la creación y reproducibilidad del archivo de video almacenado en la Raspberry.

---

### **Requisito funcional 3: Captura de evento de identificación**

* **Enunciado:** La aplicación en Python deberá detectar la recepción de una señal de entrada (pulsación de tecla en consola) en un tiempo máximo de 100 ms desde su generación. *****sujeto a cambios
* **Trazabilidad:** Caso de uso 3.
* **Método de Verificación:** Medición del tiempo de respuesta mediante marcas de tiempo en la aplicación de Python.

--- 

### **Requisito funcional 4: Registro de eventos en bitácora local** ESTE HAY QUE MODIFICARLO

* **Enunciado:** Al procesar un evento, la aplicación deberá registrar en un archivo de bitácora local en disco la fecha y hora exacta (timestamp) en formato ISO-8601 junto con el resultado de la solicitud.
* **Trazabilidad:** Caso de uso 3.
* **Método de Verificación:** Inspección (revisión del contenido del archivo de texto `.log` generado en disco).

---

### **Requisito funcional 5: Conmutación de salida de control (GPIO)**

* **Enunciado:** Al validarse una solicitud de ingreso, el sistema deberá conmutar el estado lógico de la línea GPIO durante un intervalo configurable, retornando posteriormente al estado original.
* **Trazabilidad:** Caso de uso 4.
* **Método de Verificación:** Medición del tiempo de encendido con osciloscopio.