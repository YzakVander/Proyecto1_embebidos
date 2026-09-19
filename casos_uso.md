# Especificación de Casos de Uso - Proyecto 1: Sistema de Control de Acceso
**Curso:** Taller de Sistemas Embebidos 
**Estándar usado como Referencia:** ISO/IEC/IEEE 29148:2018  

---

### **Caso de uso 1: Visualización en tiempo real (stream hacia el puesto de vigilancia)**

* **Actor Principal:** Persona en el puesto de vigilancia.
* **Propósito:** Permitir la supervisión remota del punto de acceso.
* **Recurso accesible:** Video en vivo de la cámara en la puerta.
* **Precondiciones:** La Raspberry Pi 4 se encuentra encendida, conectada a la red local y con la cámara operativa.
* **Flujo Principal:**
  1. El sistema inicia la tubería de GStreamer capturando video de la cámara.
  2. El sistema codifica la señal de video y la empaqueta para transmisión a través de la red.
  3. El puesto de vigilancia recibe el flujo multimedia en vivo en la computadora remota.
* **Postcondiciones:** El video de la entrada se transmite de forma continua y con baja latencia hacia el puesto de monitoreo.

---

### **Caso de uso 2: Extracción y consulta de evidencia en video**

* **Actor Principal:** Persona de mantenimiento / Administrador del sistema.
* **Propósito:** Recuperar los archivos de video grabados localmente en la tarjeta de la placa.
* **Precondiciones:** El sistema ha estado grabando y reteniendo evidencia en el almacenamiento local de la Raspberry Pi 4.
* **Flujo Principal:**
  1. La persona de mantenimiento solicita la extracción o consulta del archivo de video almacenado en la Raspberry Pi 4.
  2. La aplicación ubica el archivo de video registrado en el sistema de archivos local.
  3. El sistema transfiere o entrega la evidencia en video al usuario de mantenimiento.
* **Postcondiciones:** La evidencia en video queda extraída y disponible fuera del sistema para su revisión.

---

### **Caso de uso 3: Procesamiento de Evento de Identificación**

* **Actor Principal:** Persona en el puesto de vigilancia.
* **Propósito:** Evaluar visualmente la presencia de un sujeto en la puerta y resolver una solicitud de ingreso.
* **Precondiciones:** La aplicación se encuentra en ejecución transmitiendo video en vivo y monitoreando las entradas de control (teclado/consola en la computadora remota).
* **Flujo Principal:**
  1. Una persona se presenta en el punto de acceso y es observada por la persona en el puesto de vigilancia.
  2. La persona en el puesto de vigilancia presiona un botón/tecla para permitir el acceso (u otro botón para denegarlo).
  3. La aplicación de Python captura el evento de decisión, lo asocia con la marca de tiempo de la evidencia y procesa la autorización o denegación.
* **Postcondiciones:** Se registra el resultado de la solicitud y se dispara la respuesta en el lado del sujeto.

---

### **Caso de uso 4: Actuación y Control de Salida Eléctrica**

* **Actor Principal:** Sujeto que solicita acceso.
* **Propósito:** Percibir el resultado de la solicitud de ingreso mediante los LEDS de la placa.
* **Precondiciones:** El Caso de Uso 3 fue ejecutado exitosamente y los LEDS de la Raspberry 4 están disponibles.
* **Flujo Principal:**
  1. La aplicación en Python dentro de la Raspberry envía la señal de activación a la línea GPIO correspondiente según el resultado procesado.
  2. El sujeto en la puerta observa la conmutación del estado de los LEDS en la placa durante un tiempo determinado.
  3. Transcurrido el intervalo, la aplicación restablece la los LEDS a su estado de reposo.
* **Postcondiciones:** El sujeto recibe la retroalimentación visual de su solicitud.