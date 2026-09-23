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

---

### **Caso de uso 5: Denegación por vencimiento del tiempo de decisión**

* **Actor Principal:** Sujeto que solicita acceso.
* **Propósito:** Denegar el acceso por defecto (estado seguro) cuando no hay respuesta desde el puesto de vigilancia en el tiempo límite.
* **Precondiciones:** Una persona se encuentra en el punto de acceso y el sistema está a la espera de la decisión del vigilante.
* **Flujo Principal:**
  1. El sistema inicia un temporizador de espera de decisión al presentarse la solicitud de acceso.
  2. El vigilante no emite una respuesta dentro del plazo máximo definido.
  3. El sistema aplica la política por defecto, deniega el acceso y lo registra en la bitácora.
  4. El sistema desencadena la indicación de acceso denegado (LEDS) para informar al sujeto.
* **Postcondiciones:** La solicitud es rechazada automáticamente por omisión, priorizando la seguridad.

---

### **Caso de uso 6: Continuidad ante desconexión de la cámara**

* **Actor Principal:** Persona de mantenimiento / Administrador del sistema.
* **Propósito:** Garantizar que el sistema gestione correctamente la desconexión física de la cámara sin quedar en un estado indeterminado.
* **Precondiciones:** El sistema se encuentra en operación normal transmitiendo y grabando video.
* **Flujo Principal:**
  1. La cámara se desconecta físicamente en caliente de la Raspberry Pi 4.
  2. El sistema detecta la pérdida del flujo multimedia.
  3. La aplicación maneja la excepción internamente o el servicio es finalizado y reiniciado automáticamente por el administrador de servicios (systemd).
* **Postcondiciones:** El sistema aborta la operación de forma controlada y queda a la espera de recuperación al reconectarse el dispositivo, sin procesos colgados.

---

### **Caso de uso 7: Puesta en servicio tras corte de energía**

* **Actor Principal:** Persona de mantenimiento / Administrador del sistema.
* **Propósito:** Asegurar que el sistema arranque de manera autónoma y segura tras restaurarse la energía eléctrica.
* **Precondiciones:** La Raspberry Pi 4 sufrió un corte de energía y se restablece el suministro eléctrico.
* **Flujo Principal:**
  1. El hardware recibe energía y arranca el núcleo (kernel) de Linux.
  2. Durante el arranque, los LEDS/pines GPIO se mantienen en un estado inicial definido y seguro (denegado/apagado).
  3. El gestor de servicios (systemd) inicia automáticamente el servicio de la aplicación en Python.
  4. La aplicación inicializa la cámara, levanta la tubería de GStreamer y comienza a monitorear eventos.
* **Postcondiciones:** El sistema queda operando normalmente sin necesidad de intervención manual.

---

### **Caso de uso 8: Gestión del almacenamiento de evidencia**

* **Actor Principal:** Persona de mantenimiento / Administrador del sistema.
* **Propósito:** Evitar la caída del sistema por falta de espacio en disco gestionando las grabaciones de video mediante una política de retención.
* **Precondiciones:** La partición o directorio de almacenamiento de la Raspberry Pi 4 se acerca a su límite máximo de capacidad.
* **Flujo Principal:**
  1. La aplicación genera continuamente los archivos de video.
  2. El sistema detecta que el espacio disponible alcanzó el límite mínimo de almacenamiento permitido.
  3. La aplicación ejecuta la política de retención para liberar espacio de forma dinámica.
* **Postcondiciones:** Se libera espacio en el almacenamiento, permitiendo que la grabación de la evidencia continúe de forma ininterrumpida.

---

### **Caso de uso 9: Detención programada para mantenimiento**

* **Actor Principal:** Persona de mantenimiento / Administrador del sistema.
* **Propósito:** Detener la aplicación de manera ordenada garantizando que los archivos de video en curso se guarden sin corrupción.
* **Precondiciones:** El sistema se encuentra grabando video hacia el disco.
* **Flujo Principal:**
  1. La persona de mantenimiento envía una solicitud de detención del servicio en la placa.
  2. La aplicación intercepta la señal y ordena a la tubería de GStreamer cerrar el flujo multimedia.
  3. Se escriben correctamente los metadatos finales en el contenedor de video actual y el archivo se cierra.
  4. La aplicación finaliza el proceso de Python.
* **Postcondiciones:** El sistema se detiene y el último archivo de video queda íntegro, reproducible y verificable (ej. con ffprobe).

---

### **Caso de uso 10: Auditoría de la bitácora de accesos**

* **Actor Principal:** Persona de mantenimiento / Administrador del sistema.
* **Propósito:** Consultar el historial local de decisiones (permitidas o denegadas) que ha tomado el sistema.
* **Precondiciones:** Se ha ejecutado el sistema previamente, registrando decisiones, y ha sobrevivido a reinicios o cortes de energía.
* **Flujo Principal:**
  1. La persona de mantenimiento solicita la revisión del registro local (`access.log`).
  2. El sistema accede al medio de almacenamiento no volátil.
  3. El usuario lee y revisa las entradas con marcas de tiempo y el estado final de cada acceso.
* **Postcondiciones:** La bitácora se consulta exitosamente demostrando la persistencia de los eventos en el tiempo.
