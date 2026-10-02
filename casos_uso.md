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
* **Flujo Principal (extracción remota):**
  1. La persona de mantenimiento ejecuta, en la computadora de observación, un script que se conecta por SSH a la Raspberry Pi 4.
  2. El script copia los segmentos de la grabación continua (`evidencia/`) y los clips de las solicitudes (`eventos/`) a la computadora de observación.
  3. La persona de mantenimiento reproduce los videos en la computadora de observación.
* **Flujo Alterno (consulta local):**
  1. La persona de mantenimiento conecta un monitor y un teclado a la Raspberry Pi 4.
  2. La persona de mantenimiento ubica el clip o segmento en el almacenamiento local (la ruta de cada clip está registrada en la bitácora) y lo reproduce directamente en la placa.
* **Postcondiciones:** La evidencia en video queda disponible para su revisión, en la computadora de observación o en el monitor de la placa.

---

### **Caso de uso 3: Procesamiento de Evento de Identificación**

* **Actor Principal:** Persona en el puesto de vigilancia.
* **Propósito:** Evaluar visualmente la presencia de un sujeto en la puerta y resolver una solicitud de ingreso.
* **Alcance:** Persona que se presenta sin credencial QR. Si la persona porta credencial, la solicitud se abre al leerla (caso de uso 13).
* **Precondiciones:** La aplicación se encuentra en ejecución transmitiendo video en vivo y la computadora del puesto de vigilancia está conectada a la Raspberry Pi 4 por la red (canal TCP de decisiones).
* **Flujo Principal:**
  1. Una persona se presenta en el punto de acceso y es observada por la persona en el puesto de vigilancia a través del video en vivo.
  2. La persona en el puesto de vigilancia envía a la placa un mensaje de inicio de solicitud desde la computadora del puesto de vigilancia.
  3. La Raspberry Pi 4 abre la solicitud, le asigna un identificador con la fecha y hora de apertura, inicia la cuenta regresiva del plazo de decisión y lo notifica al puesto de vigilancia.
  4. Dentro del plazo, la persona en el puesto de vigilancia envía a la placa un mensaje para permitir o denegar el acceso.
  5. La Raspberry Pi 4 recibe la decisión, confirma su recepción al puesto de vigilancia, la registra en la bitácora con la marca de tiempo de la decisión y guarda un clip MP4 del evento (segundos configurables antes y después de la decisión, 5 s y 5 s por defecto), cuya ruta queda asociada al registro.
* **Postcondiciones:** Se registra el resultado de la solicitud, se notifica al puesto de vigilancia y se dispara la respuesta en el lado del sujeto (caso de uso 4). La Raspberry Pi 4 queda lista para una nueva solicitud.

---

### **Caso de uso 4: Actuación y Control de Salida Eléctrica**

* **Actor Principal:** Sujeto que solicita acceso.
* **Propósito:** Percibir el resultado de la solicitud de ingreso mediante una señal acústica.
* **Precondiciones:** El Caso de Uso 3, el Caso de Uso 5 o el Caso de Uso 13 fue ejecutado y el buzzer pasivo está conectado a la línea GPIO 18 de la Raspberry Pi 4, con el PWM de hardware habilitado.
* **Flujo Principal:**
  1. La aplicación en Python dentro de la Raspberry genera, mediante el PWM de hardware, una señal cuadrada en la línea GPIO 18 con un tono distinto según el resultado: un tono agudo continuo si se permite el acceso, o una serie de pitidos graves si se deniega.
  2. El sujeto en la puerta escucha el tono y reconoce el resultado. Simultáneamente, la aplicación muestra un mensaje con el resultado en la consola de la Raspberry Pi 4.
  3. Al terminar el tono, la aplicación restablece la salida a su estado de reposo (silencio).
* **Postcondiciones:** El sujeto recibe la retroalimentación acústica de su solicitud.

---

### **Caso de uso 5: Denegación por vencimiento del tiempo de decisión**

* **Actor Principal:** Sujeto que solicita acceso.
* **Propósito:** Denegar el acceso por defecto (estado seguro) cuando no hay respuesta desde el puesto de vigilancia en el tiempo límite.
* **Precondiciones:** Hay una solicitud abierta que requiere decisión del vigilante, ya sea iniciada por él (caso de uso 3) o escalada por la lectura de una credencial de visitante, desconocida o revocada (caso de uso 13), y el sistema está a la espera de su decisión.
* **Flujo Principal:**
  1. El sistema inicia un temporizador de espera de decisión al abrirse la solicitud de acceso.
  2. El vigilante no emite una respuesta dentro del plazo máximo definido.
  3. El sistema aplica la política por defecto, deniega el acceso, lo registra en la bitácora como denegado por vencimiento y lo notifica al puesto de vigilancia.
  4. El sistema desencadena la indicación de acceso denegado (buzzer) para informar al sujeto.
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
  2. Durante el arranque, la línea GPIO del buzzer (GPIO 18) se mantiene en un estado inicial definido y seguro (nivel bajo, en silencio).
  3. El gestor de servicios (systemd) inicia automáticamente el servicio de la aplicación en Python.
  4. La aplicación inicializa la cámara, levanta la tubería de GStreamer y comienza a monitorear eventos.
* **Postcondiciones:** El sistema queda operando normalmente sin necesidad de intervención manual.

---

### **Caso de uso 8: Gestión del almacenamiento de evidencia**

* **Actor Principal:** Persona de mantenimiento / Administrador del sistema.
* **Propósito:** Evitar la caída del sistema por falta de espacio en disco gestionando las grabaciones de video mediante una política de retención.
* **Precondiciones:** La aplicación está en ejecución y cada carpeta de evidencia tiene un tope de ocupación configurado: `evidencia/` (grabación continua) y `eventos/` (clips de las solicitudes).
* **Flujo Principal:**
  1. La aplicación genera continuamente los archivos de video.
  2. Al cerrarse cada segmento, después de cada clip y de forma periódica, el sistema compara lo que ocupa cada carpeta con su tope.
  3. Si una carpeta supera su tope, la aplicación borra sus archivos más antiguos hasta quedar por debajo: en `evidencia/` los segmentos de número más bajo y en `eventos/` los clips con la fecha más antigua en su nombre. Nunca borra el segmento en curso ni archivos de la otra carpeta.
* **Flujo Alterno (arranque tras una interrupción):**
  1. Al iniciar, antes de comenzar a grabar, la aplicación revisa los MP4 de ambas carpetas y borra los que quedaron corruptos (sin índice) por un corte de energía o un cierre forzado.
  2. La numeración de los segmentos continúa a partir del más alto existente, de modo que no se sobrescribe evidencia anterior.
* **Postcondiciones:** Cada carpeta se mantiene por debajo de su tope, permitiendo que la grabación de la evidencia continúe de forma ininterrumpida.

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
  1. La persona de mantenimiento solicita la revisión del registro local (`accesos.log`).
  2. El sistema accede al medio de almacenamiento no volátil.
  3. El usuario lee y revisa las entradas con marcas de tiempo y el estado final de cada acceso.
* **Postcondiciones:** La bitácora se consulta exitosamente demostrando la persistencia de los eventos en el tiempo.

---

### **Caso de uso 11: Registro de una credencial QR**

* **Actor Principal:** Persona en el puesto de vigilancia.
* **Propósito:** Autorizar a una persona para identificarse en el punto de acceso mediante una credencial QR.
* **Precondiciones:** La aplicación está en ejecución y la computadora del puesto de vigilancia está conectada a la Raspberry Pi 4 por el canal TCP de decisiones.
* **Flujo Principal:**
  1. La persona en el puesto de vigilancia envía a la placa el comando de alta con el rol (vigilante, mantenimiento o visitante) y el nombre de la persona.
  2. La Raspberry Pi 4 asigna un identificador aleatorio (ej. `ACC-7F3A91`), registra la credencial en el almacenamiento persistente y genera la imagen de la credencial: el QR contiene solo el identificador, y el nombre y el rol se imprimen fuera del código.
  3. La Raspberry Pi 4 relee la imagen generada y verifica que el QR se decodifique correctamente.
  4. La Raspberry Pi 4 confirma el alta al puesto de vigilancia, indicando el identificador y la ruta de la imagen.
* **Postcondiciones:** La credencial queda activa y su imagen disponible para entregarse a la persona (impresa o en pantalla).

---

### **Caso de uso 12: Revocación de una credencial QR**

* **Actor Principal:** Persona en el puesto de vigilancia.
* **Propósito:** Retirar el acceso de una persona sin perder el registro histórico de su credencial.
* **Precondiciones:** La credencial fue registrada previamente (caso de uso 11) y está activa.
* **Flujo Principal:**
  1. La persona en el puesto de vigilancia envía a la placa el comando de baja con el identificador de la credencial y, opcionalmente, el motivo.
  2. La Raspberry Pi 4 marca la credencial como inactiva y registra la fecha de la baja, conservando el registro.
  3. La Raspberry Pi 4 confirma la revocación al puesto de vigilancia.
* **Postcondiciones:** Si la credencial revocada se presenta ante la cámara, el sistema no otorga acceso automático y escala la decisión al puesto de vigilancia (caso de uso 13).

---

### **Caso de uso 13: Acceso por lectura de credencial QR**

* **Actor Principal:** Sujeto que solicita acceso.
* **Propósito:** Identificar al sujeto por su credencial QR y resolver el acceso según su rol, con intervención del vigilante solo cuando hace falta.
* **Precondiciones:** La aplicación está en ejecución con el lector de QR activo y no hay otra solicitud pendiente.
* **Flujo Principal (credencial activa de vigilante o mantenimiento):**
  1. El sujeto muestra su credencial frente a la cámara del punto de acceso.
  2. La aplicación detecta y decodifica el QR en el video en vivo y busca el identificador en el registro de credenciales.
  3. La aplicación abre la solicitud y la resuelve de inmediato como permitida, notificándolo al puesto de vigilancia.
  4. Se registra la decisión en la bitácora, se guarda el clip del evento y se indica el resultado al sujeto (caso de uso 4).
* **Flujo Alterno (credencial de visitante, desconocida o revocada):**
  1. La aplicación abre la solicitud y notifica al puesto de vigilancia que requiere su decisión.
  2. La solicitud continúa como en el caso de uso 3 desde la decisión del vigilante; si no hay respuesta dentro del plazo, se aplica el caso de uso 5.
* **Flujo Alterno (lectura repetida):**
  1. Si el mismo identificador se lee de nuevo dentro del tiempo de enfriamiento configurado (5 s por defecto), la lectura se ignora para no abrir solicitudes duplicadas.
* **Postcondiciones:** La solicitud queda resuelta y registrada con el identificador de la credencial, y la Raspberry Pi 4 queda lista para una nueva solicitud.

