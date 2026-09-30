# Especificación de Casos de Uso - Proyecto 1: Sistema de Control de Acceso
**Curso:** Taller de Sistemas Embebidos
**Estándar usado como Referencia:** ISO/IEC/IEEE 29148:2018

---

## Actores del sistema

| Actor | Descripción |
|---|---|
| **Vigilante** | Persona en el puesto de vigilancia remoto. Observa el video en vivo y resuelve las solicitudes de ingreso. |
| **Sujeto** | Persona que se presenta en el punto de acceso y solicita el ingreso. |
| **Operador de mantenimiento** | Administrador del sistema. Extrae evidencia, audita la bitácora y gestiona el equipo. |

---

### **Caso de uso 1: Visualización en tiempo real (stream hacia el puesto de vigilancia)**

* **Actor Principal:** Vigilante.
* **Propósito:** Permitir la supervisión remota del punto de acceso.
* **Recurso accesible:** Video en vivo de la cámara en la puerta.
* **Precondiciones:** La Raspberry Pi 4 se encuentra encendida, conectada a la red local y con la cámara operativa.
* **Flujo Principal:**
  1. El sistema inicia la tubería de GStreamer capturando video de la cámara USB.
  2. El sistema decodifica el flujo MJPEG entregado por la cámara y lo comprime en H.264 mediante el codificador por hardware del SoC.
  3. El sistema empaqueta el flujo comprimido en RTP y lo transmite por UDP hacia la dirección del puesto de vigilancia.
  4. El puesto de vigilancia recibe y muestra el flujo multimedia en vivo.
* **Flujo alternativo 3a:** Si el puesto de vigilancia se conecta después de iniciada la transmisión, la imagen aparece al llegar el siguiente cuadro clave, garantizado por la reinserción periódica de los parámetros de secuencia.
* **Postcondiciones:** El video de la entrada se transmite de forma continua hacia el puesto de monitoreo.

---

### **Caso de uso 2: Extracción y consulta de evidencia en video**

* **Actor Principal:** Operador de mantenimiento.
* **Propósito:** Recuperar los archivos de video grabados localmente en la tarjeta de la placa.
* **Precondiciones:** El sistema ha estado grabando y reteniendo evidencia en el almacenamiento local de la Raspberry Pi 4.
* **Flujo Principal:**
  1. El operador solicita la extracción o consulta del archivo de video almacenado en la Raspberry Pi 4.
  2. La aplicación ubica el archivo de video registrado en el sistema de archivos local.
  3. El sistema transfiere o entrega la evidencia en video al operador.
* **Postcondiciones:** La evidencia en video queda extraída y disponible fuera del sistema para su revisión.

---

### **Caso de uso 3: Procesamiento de evento de identificación**

* **Actor Principal:** Vigilante.
* **Propósito:** Evaluar visualmente la presencia de un sujeto en la puerta y resolver una solicitud de ingreso.
* **Precondiciones:** La aplicación se encuentra en ejecución transmitiendo video en vivo y monitoreando las entradas de control.
* **Flujo Principal:**
  1. Un sujeto se presenta en el punto de acceso y es observado por el vigilante a través del video en vivo.
  2. El sistema recibe la notificación de solicitud de ingreso e inicia el plazo de decisión.
  3. El vigilante emite la resolución de permitir o denegar el acceso.
  4. La aplicación captura el evento de decisión, lo asocia con una marca de tiempo y procesa la autorización o denegación.
* **Flujo alternativo 3a:** Si ya existe una solicitud en curso, la nueva solicitud se descarta y se registra el motivo.
* **Flujo alternativo 4a:** Si la resolución llega después de vencido el plazo, el sistema la rechaza; la decisión por vencimiento es definitiva (ver Caso de uso 5).
* **Postcondiciones:** Se registra el resultado de la solicitud y se dispara la respuesta en el lado del sujeto.

---

### **Caso de uso 4: Actuación y control de salida eléctrica**

* **Actor Principal:** Sujeto.
* **Propósito:** Percibir el resultado de la solicitud de ingreso mediante los indicadores luminosos de la placa.
* **Precondiciones:** El Caso de uso 3 o el Caso de uso 5 fue ejecutado y las líneas GPIO de la Raspberry Pi 4 están disponibles.
* **Flujo Principal:**
  1. La aplicación envía la señal de activación a la línea GPIO correspondiente según el resultado procesado: una línea para acceso permitido y otra para acceso denegado.
  2. El sujeto observa la conmutación del estado de los indicadores durante un intervalo configurable.
  3. Transcurrido el intervalo, la aplicación restablece los indicadores a su estado de reposo.
* **Flujo alternativo 1a:** Si ya hay un pulso de indicación en curso, la nueva indicación se descarta y se registra el motivo, evitando que dos eventos consecutivos prolonguen la señal más allá de lo previsto.
* **Postcondiciones:** El sujeto recibe la retroalimentación visual de su solicitud y las líneas GPIO retornan al estado de reposo.

---

### **Caso de uso 5: Denegación por vencimiento del tiempo de decisión**

* **Actor Principal:** Sujeto.
* **Propósito:** Denegar el acceso por omisión (estado seguro) cuando no hay respuesta desde el puesto de vigilancia dentro del plazo definido.
* **Precondiciones:** Una solicitud de ingreso se encuentra en curso y el sistema espera la decisión del vigilante.
* **Flujo Principal:**
  1. El sistema inicia el temporizador de decisión al registrarse la solicitud de acceso.
  2. El vigilante no emite resolución dentro del plazo máximo configurado.
  3. El sistema cierra la solicitud de forma definitiva, aplica la política por omisión y deniega el acceso.
  4. El sistema registra el resultado en la bitácora indicando el motivo del rechazo.
  5. El sistema desencadena la indicación de acceso denegado para informar al sujeto.
* **Postcondiciones:** La solicitud queda rechazada de forma irreversible, priorizando la seguridad. Una resolución posterior sobre la misma solicitud no tiene efecto.

---

### **Caso de uso 6: Continuidad ante desconexión de la cámara**

* **Actor Principal:** Operador de mantenimiento.
* **Propósito:** Garantizar que el sistema gestione la desconexión física de la cámara sin quedar en un estado indeterminado.
* **Precondiciones:** El sistema se encuentra en operación normal transmitiendo y grabando video.
* **Flujo Principal:**
  1. La cámara se desconecta físicamente en caliente de la Raspberry Pi 4.
  2. El sistema detecta la pérdida del flujo multimedia a través del bus de mensajes de la tubería.
  3. La aplicación registra una alerta en la bitácora del sistema.
  4. La aplicación libera la tubería y reintenta su reconstrucción de forma periódica.
  5. Al reconectarse la cámara, el sistema restablece la operación normal.
* **Flujo alternativo 4a:** Si la aplicación termina de forma anormal, el gestor de servicios la reinicia automáticamente.
* **Postcondiciones:** El sistema queda a la espera de recuperación sin procesos colgados, y se restablece automáticamente al reconectarse el dispositivo.

---

### **Caso de uso 7: Puesta en servicio tras corte de energía**

* **Actor Principal:** Operador de mantenimiento.
* **Propósito:** Asegurar que el sistema arranque de manera autónoma y segura tras restaurarse la energía eléctrica.
* **Precondiciones:** La Raspberry Pi 4 sufrió un corte de energía y se restablece el suministro.
* **Flujo Principal:**
  1. El hardware recibe energía y arranca el núcleo de Linux.
  2. Durante el arranque, las líneas GPIO de los indicadores se fijan en estado seguro mediante la configuración del gestor de arranque, antes de que inicie cualquier aplicación.
  3. El gestor de servicios inicia automáticamente el servicio de control de acceso.
  4. La aplicación inicializa la cámara, levanta la tubería de GStreamer y comienza a monitorear eventos.
* **Postcondiciones:** El sistema queda operando normalmente sin intervención manual, con los indicadores en estado de reposo desde el instante del arranque.

---

### **Caso de uso 8: Gestión del almacenamiento de evidencia**

* **Actor Principal:** Operador de mantenimiento.
* **Propósito:** Evitar la caída del sistema por falta de espacio en disco mediante una política de retención.
* **Precondiciones:** El almacenamiento de la Raspberry Pi 4 se acerca a su límite de capacidad.
* **Flujo Principal:**
  1. La aplicación genera continuamente segmentos de video cerrados e independientes.
  2. El sistema detecta que el espacio ocupado alcanzó el umbral configurado.
  3. La aplicación elimina los segmentos más antiguos para liberar espacio.
* **Postcondiciones:** Se libera espacio en el almacenamiento, permitiendo que la grabación continúe de forma ininterrumpida.

---

### **Caso de uso 9: Detención programada para mantenimiento**

* **Actor Principal:** Operador de mantenimiento.
* **Propósito:** Detener la aplicación de manera ordenada garantizando que el video en curso se guarde sin corrupción.
* **Precondiciones:** El sistema se encuentra grabando video hacia el disco.
* **Flujo Principal:**
  1. El operador solicita la detención del servicio.
  2. La aplicación intercepta la señal de terminación e inyecta un evento de fin de flujo en la tubería.
  3. El multiplexor escribe los metadatos finales en el contenedor de video y cierra el archivo.
  4. La aplicación devuelve las líneas GPIO a su estado de reposo y finaliza.
* **Postcondiciones:** El sistema se detiene, el último archivo de video queda íntegro y reproducible, y los indicadores quedan en estado seguro.

---

### **Caso de uso 10: Auditoría de la bitácora de accesos**

* **Actor Principal:** Operador de mantenimiento.
* **Propósito:** Consultar el historial local de decisiones que ha tomado el sistema.
* **Precondiciones:** El sistema ha registrado decisiones previamente y ha sobrevivido a reinicios o cortes de energía.
* **Flujo Principal:**
  1. El operador solicita la revisión del registro local de accesos.
  2. El sistema accede al medio de almacenamiento no volátil.
  3. El operador lee las entradas con sus marcas de tiempo, el identificador de la solicitud, el resultado y la latencia de decisión.
* **Postcondiciones:** La bitácora se consulta exitosamente, demostrando la persistencia de los eventos en el tiempo.
