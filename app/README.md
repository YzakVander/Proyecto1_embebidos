# Sistema de control de acceso — aplicación (Rol A)

Proyecto 1 · Taller de Sistemas Embebidos · TEC

Aplicación en Python + GStreamer que corre como servicio (`acceso-control`)
en la Raspberry Pi 4 con la imagen de Yocto de `meta-acceso`. Captura video de
una cámara USB en la entrada, lo graba como evidencia, lo transmite en vivo al
puesto de vigilancia, lee credenciales QR y resuelve cada solicitud de acceso
con un buzzer por PWM.

**Cámara:** se usa una webcam USB (UVC) con `v4l2src`, no una cámara CSI con
`libcamerasrc` como menciona el enunciado. La sustitución la autorizó el
profesor y elimina el riesgo técnico más alto del proyecto (decisión D-05 en
`../Bitacora/bitacora-daniel.md`).

## Arquitectura

Tubería (con `config/acceso.conf`, cámara USB en MJPEG y codificador por
hardware del BCM2711):

```
v4l2src ─ image/jpeg ─ queue ─ t_raw ─┬─ queue ─ v4l2jpegdec ─ v4l2convert ─ v4l2h264enc ─ level=4 ─ h264parse ─ t_h264 ─┬─ queue ─ splitmuxsink        (evidencia continua)
                                      │                                                                                ├─ queue ─ rtph264pay ─ udpsink (video al vigilante)
                                      │                                                                                └─ queue ─ h264parse ─ appsink  (buffer circular → clips)
                                      └─ queue ─ v4l2jpegdec ─ v4l2convert ─ BGR ─ appsink                                          (lector QR)
```

El video se comprime una sola vez y el flujo H.264 se reparte. Cada salida de
tee lleva su propia queue. La justificación de cada capsfilter y de cada queue
está en `mediciones/A4-B2-justificaciones.md`.

Hilos (H1): el trabajo lento (lector QR, espera de la decisión, bitácora,
clips, retención, buzzer) corre fuera de los hilos de GStreamer, que solo
copian bytes en los callbacks de los appsink y nunca esperan. Los nueve tipos
de hilo, el diagrama y los puntos de sincronización están en
`../docs/H1-arquitectura-hilos.md`.

## Módulos

Requisitos (RF/RNF) y casos de uso (CU) según `requisitos_funcionales.md` y
`casos_uso.md`; ítems de letra y número (A1, B4, E4…) según el acta de
validación del pipeline.

| Archivo | Responsabilidad | Requisitos / CU | Ítems del acta |
|---|---|---|---|
| `__main__.py` | punto de entrada (`python3 -m acceso`), argumentos de consola | — | A6 (`--dot`), H6 (`--ver-bitacora`) |
| `config.py` | configuración INI sin dependencias externas; valores configurables de los requisitos | RF-5, RF-6, RF-7, RF-12 | — |
| `pipeline.py` | tubería GStreamer, appsink de clips y de QR, watch del bus, cambio de destino del streaming, cierre ordenado | RF-1, RF-2, RF-11, RNF-2 | A*, B*, E1, E4, B6 |
| `buffer_circular.py` | pre-evento en cuadros H.264 comprimidos y escritura de los clips MP4 | RF-2, CU-3 | B4, B5 |
| `servicio.py` | orquestación e hilos, procesamiento de comandos y solicitudes | RF-13, CU-3, CU-5, CU-13, RNF-4 | H1, E2, E3, B6 |
| `decision.py` | plazo de decisión con denegación por vencimiento y bitácora persistente | RF-4, RF-6, RF-8, CU-5, CU-10 | H2, H6 |
| `red.py` | canal TCP con el puesto de vigilancia (puerto 5001) | RF-3, CU-3 | — |
| `actuador.py` | buzzer pasivo en GPIO 18 por PWM de hardware y mensaje en consola | RF-5, RF-9, CU-4 | H5 |
| `lector_qr.py` | detección de credenciales QR con OpenCV en su propio hilo | RF-12, CU-13 | H1 |
| `registro.py` | registro persistente de credenciales y sus roles | RF-13, RF-14, CU-11, CU-12 | — |
| `credencial.py` | generación y verificación de la imagen de la credencial | CU-11 | — |
| `retencion.py` | topes por carpeta y borrado de MP4 corruptos al arrancar | RF-7, CU-8 | E4, H7 |

## Prototipado con gst-launch-1.0

Las tuberías se diseñaron primero en la consola, con `gst-launch-1.0` en la
computadora de desarrollo, usando `videotestsrc` y `x264enc` en lugar de la
cámara y el codificador por hardware. Lo que se aprendió ahí quedó en
`mediciones/`:

| Prototipo | Hallazgo | Evidencia |
|---|---|---|
| Fuente sin formato fijo | `videotestsrc` negocia `Y444_10LE` y `x264enc` sale en perfil 4:4:4, que casi ningún reproductor decodifica: los caps se leen, no se suponen | `A1-sin-formato.txt`, `A1-con-formato.txt` |
| Tee con y sin queue | sin queue, la rama lenta frena a la rápida: 122 s contra 38 s para 150 cuadros | `B1-tee-queue.txt` (`scripts/b1-tee.sh`) |
| Latencia con el tracer | 12–21 ms de la fuente al `udpsink`; corrigió un presupuesto estimado en 605 ms | `D1-tracer.txt`, `D4-presupuesto.md` |
| Rama de clips por appsink | un tee impone las mismas caps a todas sus ramas; sin `byte-stream` el clip no se relee | `B4-B5-buffer-circular.txt` |

**En la placa el prototipado por consola tiene un límite.** El bloque
`bcm2835-codec` (decodificador JPEG, ISP y codificador H.264) no admite
instancias externas mientras `acceso-control` lo usa: un `gst-launch-1.0`
con `v4l2jpegdec`, `v4l2convert` o `v4l2h264enc` falla con
`bcm2835_codec_start_streaming: Failed enabling i/p port, ret -3`
(`mediciones/C1-hallazgo-contextos.txt`). Para probar una tubería a mano hay
que detener el servicio y esperar unos 10 s. Por eso las mediciones en la
placa se hacen desde la aplicación misma, con su configuración real:
`scripts/a6-grafo.sh` (grafo y caps negociados) y `scripts/d1-latencia.sh`
(tracer de latencia), que detienen y vuelven a arrancar el servicio solos.

## Uso

### En la placa (imagen de Yocto)

El servicio arranca solo con systemd. Configuración en `/etc/acceso/acceso.conf`
y datos en `/var/lib/acceso/` (evidencia, clips, bitácora y credenciales).

```bash
systemctl status acceso-control
journalctl -u acceso-control -f            # log en vivo
systemctl restart acceso-control           # tras cambiar la configuración

acceso-control --mostrar-tuberia           # la tubería sin ejecutarla
acceso-control --ver-bitacora              # bitácora de accesos (H6)
```

### Desde el puesto de vigilancia (otra computadora)

Hay dos clientes; los dos abren el video en vivo y se conectan al canal de
comandos (TCP 5001). Al conectarse, la placa redirige el video a la IP de esa
computadora.

Requisitos en esa computadora: `python3-tk`, `python3-opencv`,
`gstreamer1.0-tools` y los plugins `good`, `bad` y `libav`.

**Interfaz gráfica** (`scripts/puesto-vigilancia.py`):

```bash
python3 scripts/puesto-vigilancia.py --ip <IP de la placa>
```

| Pestaña | Qué tiene |
|---|---|
| Operación | `SOLICITUD`, `ESTADO`, `PERMITIR`, `DENEGAR` y comando libre |
| Credenciales | alta (mantenimiento o visitante), `LISTAR`, `BAJA` y `REGENERAR_QR`. La imagen de la credencial nueva se trae a esta computadora y se abre sola |
| Galería de QR | miniaturas de las credenciales; doble clic para verlas |
| Clips de eventos | los clips de cada solicitud; doble clic para reproducirlos |
| Evidencia | RECOLECTAR y BORRAR (ver la tabla de abajo) |
| Mediciones | RF-1 (cuadros por segundo recibidos) y RF-3 (20 `PING`), con veredicto y archivo de evidencia |

Las imágenes que trae quedan en `recibidos/` y `.cache-miniaturas/`, en la
carpeta desde donde se ejecuta; `.gitignore` las excluye porque un QR de
mantenimiento abre la puerta.

**Consola** (`scripts/vigilancia.py`), con los comandos de la tabla:

```bash
./scripts/vigilancia.py --ip <IP de la placa>
```

| Comando | Qué hace |
|---|---|
| `SOLICITUD [id]` | abre una solicitud a mano (persona sin credencial) |
| `PERMITIR` / `DENEGAR` | resuelve la solicitud pendiente (plazo de 30 s) |
| `ESTADO` | solicitud pendiente y plazo restante |
| `ALTA <rol> <nombre>` | registra una credencial QR (vigilante, mantenimiento, visitante) |
| `BAJA <id> [motivo]` | revoca una credencial |
| `LISTAR` | credenciales activas |
| `REGENERAR_QR` | rehace las imágenes de las credenciales activas |
| `BORRAR_CREDENCIALES` | elimina todas las credenciales (pide confirmación) |
| `PING` | mide el tiempo de ida y vuelta (RF-3) |
| `RECOLECTAR` | trae evidencia, clips, bitácora y QR activos a `~/recoleccion/` |
| `BORRAR_VIDEOS_LOG` | borra en la placa evidencia, clips y bitácora (pide confirmación) |
| `AYUDA` / `SALIR` | lista de comandos / cerrar el cliente |

Sin el cliente, el canal acepta los mismos comandos con `nc <IP de la placa> 5001`,
y el video se puede ver con `./scripts/receptor-vigilancia.sh 5000`.

### En la computadora de desarrollo

```bash
python3 -m acceso -c config/acceso.conf --mostrar-tuberia
python3 -m acceso -c config/acceso.conf --dot grafos     # exporta el grafo (A6)

# comandos locales por FIFO, desde otra terminal
echo "SOLICITUD ID-001" > /tmp/acceso-eventos
echo "PERMITIR"         > /tmp/acceso-eventos
```

## Decisiones de diseño registradas

- **Cuadros comprimidos en el búfer**: la deque guarda hasta 450 cuadros H.264 (10 s × 1.5 de holgura), 4.5 MiB medidos en la placa, contra ~620 MB que ocuparían en crudo. Exige recortar en cuadro clave, resuelto retrocediendo al IDR anterior.
- **H2, vencimiento definitivo**: al vencer el plazo la solicitud se cierra. Un `PERMITIR` tardío es rechazado; de lo contrario la puerta se abriría después de que el sistema ya denegó.
- **E3, reconexión con alerta**: el proceso no muere; registra la alerta y reintenta cada 5 s indefinidamente.
- **H6, archivo JSONL con `fsync`**: sobrevive a corte de energía, no solo a cierre ordenado. Se inspecciona con `cat`.
- **E4 / B6, la grabación recibe su propio EOS al detener**: en la RPi 4 el EOS enviado a la fuente no termina de atravesar la cadena V4L2 de hardware y el último segmento quedaba sin índice. Se inyecta un EOS directo en la queue de grabación y se espera la confirmación de `splitmuxsink` (ver `pipeline.detener()`).
- **B6, clips pendientes al detener**: si el servicio se detiene mientras un clip espera sus segundos posteriores, se escribe con lo que haya en el búfer en vez de perderse.
- **H7, retención de datos**: qué se guarda, cuánto dura y quién accede, en `../docs/politica-de-retencion.md`.
