# Política de retención de datos (H7)

Qué almacena el sistema de control de acceso, para qué, por cuánto tiempo, quién
puede consultarlo y cómo se elimina.

> El acta lo plantea así: *un sistema que reconoce personas y no responde esta
> pregunta está incompleto, aunque el pipeline funcione.* Este sistema graba a
> todo el que pasa por la entrada y asocia nombres con horas de ingreso, así
> que la pregunta aplica de lleno.

Valores tomados de `app/config/acceso.conf`. Tasa de grabación medida en la
placa por el Rol B: **~17.4 MB/min ≈ 1050 MB/h** a 1280×720, 2.5 Mbit/s.

---

## 1. Inventario

Todo vive en la placa bajo `/var/lib/acceso/` (`StateDirectory` de systemd,
persiste entre reinicios).

| Dato | Ubicación | Datos personales | Propósito |
|---|---|---|---|
| Grabación continua | `evidencia/evidencia_NNNNN.mp4` (segmentos de 60 s) | Imagen de toda persona que pasa frente a la cámara, tenga o no una solicitud | Evidencia de lo ocurrido en la entrada, incluso fuera de un evento (CU-2, RF-2) |
| Clips de evento | `eventos/evento_<fecha>_<id>.mp4` (~10 s) | Imagen de la persona que solicitó el acceso. El **nombre** de la persona aparece en el nombre del archivo cuando entró con QR | Evidencia de cada decisión de acceso, asociada a su registro en la bitácora (CU-3) |
| Bitácora de accesos | `accesos.log` (JSONL, una línea por decisión) | Identificador, **nombre** (si entró con QR), resultado y hora exacta: un registro de quién entró y cuándo | Auditoría de decisiones (CU-10, RF-4, RF-8) |
| Registro de credenciales | `credenciales.json` | Nombre completo, rol, fecha de alta y de baja, motivo de la baja | Resolver un QR a una persona y su rol (CU-11, CU-12, RF-14) |
| Imágenes de credenciales | `credenciales/ACC-XXXXXX.bmp` | Código QR con el identificador; nombre y rol impresos fuera del código | Entregarle la credencial a la persona (CU-11) |

**Lo que el sistema NO almacena:** ni audio, ni rasgos biométricos, ni
plantillas faciales. El lector de QR analiza cuadros en memoria y los descarta;
no guarda imágenes del análisis.

---

## 2. Período de retención efectivo

| Dato | Mecanismo | Retención efectiva |
|---|---|---|
| Grabación continua | Tope de **5500 MB** (`[grabacion] max_megabytes`). Al superarlo se borran los segmentos más antiguos (RF-7, CU-8) | 5500 MB ÷ 1050 MB/h ≈ **5.2 h** de video continuo. El segmento más viejo disponible tiene unas 5 horas |
| Clips de evento | Tope de **1000 MB** (`[clips] max_megabytes`), independiente del anterior. Se borran primero los clips con la fecha más antigua | Un clip de 10 s pesa ~2.9 MB → unos **340 clips**. Depende de cuántos eventos haya: a 50 eventos por día, ~7 días; a 10 por día, ~1 mes |
| Bitácora de accesos | **Sin tope** (decisión, ver §3) | Indefinida, hasta que se borre a mano |
| Registro de credenciales | Sin tope. Una baja **no borra** la credencial: la marca inactiva y la conserva como historial (RF-14) | Indefinida |
| Imágenes de credenciales | Se generan al dar de alta. Una baja no borra la imagen; `REGENERAR_QR` borra las de credenciales inactivas | Hasta el siguiente `REGENERAR_QR` o `BORRAR_CREDENCIALES` |

**Por qué la grabación continua solo dura ~5 h.** Es la consecuencia del
espacio disponible en la microSD, no una elección de plazo. Si se necesita
más historial, hay que bajar la tasa de bits (a 0.8 Mbit/s serían ~15 h) o
extraer la evidencia antes de que se borre (§4). Lo importante para quien
opera el sistema: **un incidente que no se revisa dentro de unas 5 horas
pierde su grabación continua**, y queda solo el clip del evento si hubo
solicitud.

**Archivos que no se borran aunque haya que liberar espacio:** el segmento que
se está grabando y cualquier archivo modificado hace menos de 10 s
(`EDAD_MINIMA_S` en `retencion.py`), para no borrar un clip mientras se
escribe.

---

## 3. Decisión: la bitácora de accesos no tiene tope

Las dos carpetas de video tienen tope; la bitácora no. Es una decisión
tomada, no un olvido:

- **El tamaño no es un problema.** Cada línea pesa ~265 bytes (medido sobre
  `docs/evidencia-qr-accesos.log`). Con 1000 eventos por día, que es mucho más
  de lo que tiene una entrada real, la bitácora crece ~265 KB por día y
  **~97 MB por año**. La partición tiene 8 GiB de espacio extra
  (`IMAGE_ROOTFS_EXTRA_SPACE` en `acceso-image.bb`); después de los dos topes
  de video (6500 MB) quedan ~1.7 GB, que la bitácora tardaría más de 15 años
  en llenar a ese ritmo.
- **Es el registro de auditoría.** Su propósito es responder "¿quién entró y
  cuándo?" semanas o meses después. Rotarla o recortarla eliminaría justamente
  lo que la hace útil.
- **Se escribe con `fsync`** en cada decisión, para que sobreviva a un corte
  de energía (RF-8, H6).

**Revisión:** si la placa se usara durante años sin extraer nada, conviene
revisar el tamaño una vez al año (`ls -lh /var/lib/acceso/accesos.log`) y
archivarla con `recolectar-evidencia.sh`.

---

## 4. Quién tiene acceso y por qué vía

| Vía | Qué permite | Quién |
|---|---|---|
| Canal TCP 5001 (`puesto-vigilancia.py`, `vigilancia.py` o `nc`) | `LISTAR` muestra nombres y roles de las credenciales activas. `ALTA`, `BAJA`, `REGENERAR_QR` y `BORRAR_CREDENCIALES` las modifican | El puesto de vigilancia |
| SSH a la placa | Lectura y borrado de todo `/var/lib/acceso/` | Mantenimiento / administrador |
| `recolectar-evidencia.sh` (o RECOLECTAR en `puesto-vigilancia.py` y en `vigilancia.py`) | Copia a la computadora de observación, en `~/recoleccion/`: la evidencia, los clips, la bitácora y las imágenes QR de las credenciales **activas** | Mantenimiento / administrador |
| BORRAR en `puesto-vigilancia.py` o `BORRAR_VIDEOS_LOG` en `vigilancia.py` | Borra en la placa la evidencia, los clips y la bitácora (pide confirmación; no toca las credenciales) | Mantenimiento / administrador |
| Transmisión RTP/UDP | Video en vivo, sin cifrar | Quien esté en la IP de destino |
| Consola local (monitor y teclado en la placa) | Todo lo anterior | Quien tenga acceso físico |

**Copias fuera de la placa.** Lo que se extrae a `~/recoleccion/` sale del
alcance de esta política: la retención de la placa no lo borra, y cada
ejecución del script reemplaza la copia anterior. Quien extrae la evidencia es
responsable de esa copia.

---

## 5. Las imágenes QR son credenciales, no fotografías

Un QR de vigilante o mantenimiento **abre la puerta sin intervención del
vigilante**. Quien tenga la imagen (impresa, en pantalla o copiada) tiene ese
acceso. Por eso:

- No se suben al repositorio. `recolectar-evidencia.sh` las deja en
  `~/recoleccion/QR/`, fuera del repositorio, para que un `git add` no las
  publique por accidente. Los clientes de vigilancia, en cambio, copian las
  imágenes a la carpeta desde donde se ejecutan (`recibidos/` y
  `.cache-miniaturas/` en `puesto-vigilancia.py`, `credenciales-recibidas/` en
  `vigilancia.py`); por eso `.gitignore` excluye esas carpetas y los `*.bmp`.
- La forma de invalidar una credencial filtrada es `BAJA <id>`: el
  identificador deja de resolver a una persona aunque la imagen siga
  circulando. Regenerar la imagen **no** sirve, porque conserva el mismo
  identificador.
- El QR contiene solo el identificador (`ACC-7F3A91`). Una foto del código no
  revela el nombre ni el rol; esos datos viven solo en la placa.

---

## 6. Qué pasa al dar de baja a una persona

- La credencial queda **inactiva**, con fecha y motivo de baja, y se conserva
  como historial (RF-14). Si su QR se presenta, la solicitud se escala al
  vigilante (CU-12).
- **Su video anterior no se borra.** Los segmentos y clips en que aparece
  siguen hasta que la retención los elimine por antigüedad (~5 h la grabación
  continua, días o semanas los clips).
- **Su nombre sigue en la bitácora** y en el nombre de sus clips, porque son
  el registro de lo que ocurrió.
- Para eliminarla por completo del registro de credenciales está
  `BORRAR_CREDENCIALES SI`, que vacía **todo** el registro, no una persona.
  No existe un borrado individual.

---

## 7. Limitaciones conocidas

1. **El nombre de la persona sale del registro.** Cuando alguien entra con
   QR, la solicitud se etiqueta como `ACC-XXXXXX-Nombre_Apellido`
   (`servicio.py`, `_al_detectar_qr`). Esa etiqueta queda en la bitácora y en
   el nombre del clip. Así la bitácora se lee sin cruzarla con
   `credenciales.json`, pero el nombre queda copiado en dos lugares más, que
   tampoco se borran al dar de baja a la persona.
2. **El canal TCP no se autentica.** Si `red_clientes` en `acceso.conf` queda
   vacío (el valor actual), cualquier equipo de la red puede pedir `LISTAR` y
   ver los nombres, o dar de alta una credencial. Para la operación debe
   contener solo la IP del puesto de vigilancia.
3. **La imagen de desarrollo deja a root sin contraseña** por SSH
   (`acceso-image-dev.bb`). Con eso, cualquiera en la red puede leer o borrar
   todo lo de este inventario. La imagen de entrega (`acceso-image.bb`) ya no
   lo trae (G2), pero todavía no define otra forma de entrar a la placa; las
   funciones del puesto de vigilancia que usan SSH (recolectar, borrar y
   traer las imágenes QR) dependen de cómo se resuelva.
4. **El video viaja sin cifrar.** RTP sobre UDP en la red local. Aceptable en
   la red del laboratorio, no en una red compartida.
