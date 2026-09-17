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
* **Precondiciones:** La aplicación en Python se encuentra en ejecución monitoreando las fuentes de eventos de entrada.
* **Flujo Principal:**
  1. Ocurre una solicitud de acceso (simulada por teclado/consola en PC o mediante un evento de entrada).
  2. La aplicación de Python captura el evento y verifica el estado de la solicitud.
  3. La aplicación asocia el instante de la identificación con el flujo de evidencia y autoriza la apertura.
* **Postcondiciones:** Se valida la solicitud y se activa la rutina de apertura del acceso.

---

### **CU-04: Actuación y Control de Salida Eléctrica**

* **Actor Principal:** Sistema (Módulo de actuación GPIO).
* **Propósito:** Accionar físicamente el mecanismo de apertura (módulo de relevador) tras la validación de un evento.
* **Precondiciones:** El módulo de relevador está conectado a los pines GPIO de la Raspberry Pi 4 y el CU-03 fue ejecutado exitosamente.
* **Flujo Principal:**
  1. La aplicación en Python envía una señal de conmutación a la línea GPIO mediante la librería de control (`libgpiod`).
  2. El pin GPIO cambia de estado, activando el relevador por un tiempo determinado (e.g., pulso de apertura).
  3. Transcurrido el intervalo, la aplicación restablece el pin GPIO a su estado de reposo y registra el evento.
* **Postcondiciones:** La salida eléctrica de apertura se acciona y se cierra automáticamente, volviendo al estado seguro.