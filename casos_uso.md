# Especificación de Casos de Uso - Proyecto 1: Sistema de Control de Acceso
**Curso:** Taller de Sistemas Embebidos 
**Estándar usado como Referencia:** ISO/IEC/IEEE 29148:2018  

---

### **Caso de uso 1: Visualización en tiempo real (stream hacia el puesto de vigilancia)**

* **Actor Principal:** Persona en el puesto de vigilancia.
* **Propósito:** Permitir la supervisión remota del punto de acceso.
* **Precondiciones:** La Raspberry Pi 4 se encuentra encendida, conectada a la red local y con la cámara operativa.
* **Flujo Principal:**
  1. El sistema inicia la tubería de GStreamer capturando video de la cámara.
  2. El sistema codifica la señal de video y la empaqueta para transmisión a través de la red.
  3. El puesto de vigilancia recibe el flujo multimedia en vivo en la computadora remota.
* **Postcondiciones:** El video de la entrada se transmite de forma continua y con baja latencia hacia el puesto de monitoreo.

---

### **Caso de uso 2: Grabación y almacenamiento de video**

* **Actor Principal:** Sistema (Proceso de fondo de la aplicación).
* **Propósito:** Almacenar en un medio local no volátil el video.
* **Precondiciones:** Existe espacio suficiente de almacenamiento en el medio de destino de la Raspberry Pi 4.
* **Flujo Principal:** (esto hay que revisarlo después*****)
  1. La aplicación utiliza un elemento de bifurcación (`tee`) en GStreamer para duplicar la fuente de captura.
  2. El flujo secundario se direcciona hacia el codificador H.264 por hardware (`v4l2h264enc`).
  3. El sistema empaqueta el flujo codificado en un contenedor de video y lo guarda en disco de manera continua o fragmentada.
* **Postcondiciones:** La evidencia en video queda almacenada en el sistema de archivos local para ser consultada posteriormente.

---

### **Caso de uso 3: Procesamiento de Evento de Identificación**

* **Actor Principal:** Usuario que solicita acceso y persona en puesto de vigilancia.
* **Propósito:** Registrar y validar una solicitud de ingreso en el punto de acceso.
* **Precondiciones:** La aplicación en Python se encuentra en ejecución monitoreando las fuentes de eventos de entrada. Por simplicidad, puede ser simplemente presionar una tecla en la computadora remota.
* **Flujo Principal:**
  1. Ocurre una solicitud de acceso.
  2. La aplicación de Python captura el evento.
  3. La aplicación asocia el instante de la identificación con el flujo de evidencia y autoriza la apertura.
* **Postcondiciones:** Se valida la solicitud y se activa la rutina de apertura del acceso.

---

### **Caso de uso 4: Actuación y Control de Salida Eléctrica**

* **Actor Principal:** Sistema (control de GPIO).
* **Propósito:** Accionar físicamente el mecanismo de apertura (módulo de relevador) tras la validación de un evento. Por ahora se puede simular simplemente prendiendo un LED.
* **Precondiciones:** Los pines GPIO de la Raspberry Pi 4 están disponibles y el caso de uso 3 fue ejecutado exitosamente.
* **Flujo Principal:**
  1. La aplicación en Python envía una señal de activación a la placa que modifica el estado de algún GPIO.
  2. El pin GPIO cambia de estado, activando el LED por un tiempo determinado.
  3. Transcurrido el intervalo, la aplicación restablece el pin GPIO a su estado de reposo y registra el evento.
* **Postcondiciones:** Después de haber indicado el acceso permitido con el LED se retorna al estado inicial.