# Guion de sesión en la placa — Rol A

Todo lo del acta que al Rol A le falta medir en la Raspberry Pi 4, en el
orden que menos tiempo pierde: primero lo que no altera nada, al final lo
destructivo (disco lleno, reinicio, corte de energía).

Fecha: ______  Hora inicio: ______  Hora fin: ______  IP de la placa: ______________

**Convenciones**
- `[placa]` se corre en la Raspberry como root. `[PC]` en la laptop, desde la
  raíz del repositorio en la rama `Isaac` al día.
- Las salidas que se traen al repo van a `app/mediciones/` con el nombre que
  indica cada paso.
- La FIFO local de la placa es `/tmp/acceso-eventos`. Desde la laptop se
  puede usar `./app/scripts/vigilancia.py --ip <IP>` o `nc <IP> 5001`.
- **El bloque de hardware no admite dos procesos** (`ret -3`,
  `C1-hallazgo-contextos.txt`): nada de `gst-launch` con elementos `v4l2*`
  mientras `acceso-control` corre. Los scripts de medición ya detienen el
  servicio y lo vuelven a arrancar solos.

**Qué traer:** webcam USB, buzzer en GPIO 18, laptop con `ffmpeg` y GStreamer
(receptor), un segundo dispositivo con cronómetro en milisegundos (celular),
algo para tapar la luz.

---

## 0. Instalar el código actual en la placa (10 min)

La imagen trae una versión anterior de la aplicación. Se actualizan los
módulos sin recompilar la imagen.

    [PC]    scp app/acceso/*.py root@<IP>:/usr/lib/python3.14/site-packages/acceso/
    [PC]    ssh root@<IP> mkdir -p /root/scripts
    [PC]    scp app/scripts/{a6-grafo.sh,analizar-dot.py,d1-latencia.sh,g1-plugins.sh} root@<IP>:/root/scripts/
    [placa] chmod +x /root/scripts/*.sh
    [placa] systemctl restart acceso-control && sleep 5
    [placa] journalctl -u acceso-control -n 20

- [ ] El servicio arranca sin errores
- [ ] Commit de la rama `Isaac` instalado: ______

---

## 1. Mediciones sin alterar el sistema (30 min)

### 1.1 Grafo de la tubería real — A1, A2, A5, A6, B1, B3

    [placa] cd /root/scripts && ./a6-grafo.sh
    [PC]    scp root@<IP>:/tmp/grafos/acceso.dot app/grafos/acceso-rpi4.dot
    [PC]    scp root@<IP>:/tmp/grafos/A1-A6-grafo-rpi4.txt app/mediciones/
    [PC]    dot -Tsvg -Grankdir=LR app/grafos/acceso-rpi4.dot -o app/grafos/pipeline-acceso-rpi4.svg

- [ ] Informe generado
- [ ] A2: formato que llega a `v4l2h264enc`: ______ (¿lo entrega ya `v4l2jpegdec`? → C4 §3.2)
- [ ] A5: conversores en el grafo: ______ (esperados: 2 `v4l2jpegdec` + 2 `v4l2convert`)
- [ ] B1: todas las salidas de tee con `[OK]`

### 1.2 Latencia con el tracer — D1, D4 (y B5 con carga del tracer)

    [placa] cd /root/scripts && ./d1-latencia.sh
    [PC]    scp root@<IP>:/tmp/d1/D1-resumen-rpi4.txt app/mediciones/

- [ ] Fuente → `tx` (vigilante): p50 ______ ms  p99 ______ ms
- [ ] Etapa más lenta: ______ (______ ms)

### 1.3 Plugins — G1

    [placa] systemctl stop acceso-control && sleep 10
    [placa] cd /root/scripts && ./g1-plugins.sh > /tmp/G1-plugins.txt; systemctl start acceso-control
    [PC]    scp root@<IP>:/tmp/G1-plugins.txt app/mediciones/

`packagegroup-acceso.bb` ya cita `app/mediciones/G1-plugins.txt` como
trazabilidad: este paso crea ese archivo.

- [ ] Los cinco `v4l2*` aparecen (no "no disponible")

### 1.4 Memoria con el búfer circular lleno — B4

Con el servicio corriendo al menos 1 minuto:

    [placa] PID=$(systemctl show -p MainPID --value acceso-control)
    [placa] grep -E 'VmRSS|VmHWM' /proc/$PID/status | tee /tmp/B4-memoria-rpi4.txt

- [ ] VmRSS: ______  VmHWM: ______

### 1.5 Callbacks sin tracer — B5, C4 §3.1

Con el servicio corriendo al menos 2 minutos y una credencial QR frente a la
cámara un rato (para que la rama QR trabaje):

    [placa] systemctl stop acceso-control
    [placa] journalctl -u acceso-control -n 40 | grep "B5 callback" | tee /tmp/B5-callbacks-rpi4.txt
    [placa] systemctl start acceso-control

- [ ] clips p99: ______ ms   qr p99: ______ ms   (umbral: 3 ms)

---

## 2. Cierre ordenado y clips — E4, B6 (15 min)

### 2.1 E4: el último segmento queda reproducible

    [placa] systemctl stop acceso-control
    [placa] journalctl -u acceso-control -n 15 | tee /tmp/E4-cierre-corregido.txt
    [placa] U=$(ls -t /var/lib/acceso/evidencia/*.mp4 | head -1)
    [placa] python3 -c "from acceso.retencion import es_mp4_sano; print('$U', es_mp4_sano('$U'))" | tee -a /tmp/E4-cierre-corregido.txt
    [placa] systemctl start acceso-control && sleep 3
    [placa] journalctl -u acceso-control -n 30 | grep -i "corrupt" | tee -a /tmp/E4-cierre-corregido.txt

- [ ] Log dice `segmento cerrado al detener` y **no** `no llego EOS en 10.0 s`
- [ ] `es_mp4_sano` → `True`
- [ ] Al arrancar: `0 corruptos borrados`

### 2.2 B6: clip pendiente al detener

    [placa] echo "SOLICITUD ID-B6" > /tmp/acceso-eventos; sleep 1; echo "PERMITIR" > /tmp/acceso-eventos
    [placa] sleep 1; systemctl stop acceso-control
    [placa] tail -1 /var/lib/acceso/accesos.log
    [placa] ls -l /var/lib/acceso/eventos/ | tail -2
    [placa] journalctl -u acceso-control -n 20 | grep -E "deteniendose|clip escrito" | tee /tmp/B6-clip-al-detener.txt
    [placa] systemctl start acceso-control

- [ ] El clip que anota la bitácora existe en `eventos/`

---

## 3. Pruebas de falla (40 min)

### 3.1 Cámara desconectada en caliente — E2, H3 caso 1

    [placa] journalctl -u acceso-control -f | tee /tmp/E2-desconexion.txt

En otra terminal:
1. Desconectar la webcam. Esperar 20 s.
2. Durante la desconexión, desde la laptop: `ESTADO`, y luego `SOLICITUD` +
   `PERMITIR` (¿se anota en la bitácora?, ¿qué clip se escribe?).
3. `[placa] ls /dev/video*`: anotar con qué nodo vuelve la cámara al reconectarla.
4. Reconectar. Esperar 20 s.
5. `[placa] ls /var/lib/acceso/evidencia/ | tail -5`: la numeración no debe repetirse.

- [ ] Registra la alerta y reintenta cada 5 s, sin morir
- [ ] El canal de vigilancia responde durante la falla
- [ ] El buzzer no suena solo
- [ ] Al reconectar se recupera. Nodo al volver: ______ (si no es `/dev/video0`, la reconexión falla para siempre: anotarlo)
- [ ] Numeración de segmentos continua

### 3.2 Clasificador colgado — H2 (y H1)

Se cuelga a propósito el lector QR con un `sleep` temporal en la copia
instalada, nunca en el repo:

    [placa] L=/usr/lib/python3.14/site-packages/acceso/lector_qr.py
    [placa] cp $L /root/lector_qr.py.orig
    [placa] sed -i 's/^    def _analizar(self, cuadro: np.ndarray) -> None:/&\n        time.sleep(120)  # PRUEBA H2/' $L
    [placa] grep -n "PRUEBA H2" $L && systemctl restart acceso-control

Con una credencial frente a la cámara unos segundos (para que el lector
entre al `sleep`):
1. El video sigue llegando al receptor.
2. `[placa] ls -l /var/lib/acceso/evidencia/ | tail -2`: el segmento en curso sigue creciendo.
3. `SOLICITUD` sin responder; a los 30 s:
   `[placa] tail -1 /var/lib/acceso/accesos.log | tee /tmp/H2-clasificador-colgado.txt`

Restaurar **siempre**:

    [placa] cp /root/lector_qr.py.orig $L && systemctl restart acceso-control

- [ ] Video y grabación siguen con el lector colgado
- [ ] La solicitud queda `denegado_por_vencimiento`
- [ ] `lector_qr.py` restaurado

### 3.3 Proceso congelado con el buzzer sonando — H3 caso 2

    [placa] P=$(systemctl show -p MainPID --value acceso-control)
    [placa] echo "SOLICITUD ID-CUELGUE" > /tmp/acceso-eventos; echo "PERMITIR" > /tmp/acceso-eventos; kill -STOP $P

(El tono de permitido dura 800 ms: el `kill -STOP` tiene que entrar antes.)
Observar 30 s, y luego:

    [placa] systemctl is-active acceso-control     # systemd no lo detecta: sigue "active"
    [placa] kill -CONT $P

- [ ] ¿El buzzer quedó sonando mientras el proceso estaba congelado? ______
- [ ] ¿Se calló solo al reanudar? ______

### 3.4 Disco lleno — E5

La retención no controla un archivo ajeno: se llena el disco con uno.

    [placa] journalctl -u acceso-control -f | tee /tmp/E5-disco-lleno.txt &
    [placa] df -m /var/lib/acceso
    [placa] N=$(( $(df -m /var/lib/acceso | awk 'NR==2 {print $4}') - 20 ))
    [placa] fallocate -l ${N}M /var/lib/acceso/lastre || dd if=/dev/zero of=/var/lib/acceso/lastre bs=1M count=$N
    [placa] echo "SOLICITUD ID-DISCO" > /tmp/acceso-eventos; sleep 1; echo "PERMITIR" > /tmp/acceso-eventos
    [placa] sleep 90; tail -2 /var/lib/acceso/accesos.log
    [placa] rm /var/lib/acceso/lastre; sleep 90

- [ ] ¿Qué hizo la grabación con el disco lleno? ______
- [ ] ¿Se anotó la decisión en la bitácora? ______
- [ ] ¿El servicio murió y systemd lo reinició? ______
- [ ] ¿Se recuperó solo al liberar espacio? ______

---

## 4. Latencia extremo a extremo y carga (30 min)

### 4.1 Cronómetro filmado — D2

1. `[PC]` receptor: `./app/scripts/receptor-vigilancia.sh 5000` (anotar su
   `rtpjitterbuffer latency`: ______ ms).
2. Cronómetro con milisegundos en el celular, frente a la cámara.
3. Foto que muestre en el mismo cuadro el celular y la ventana del receptor.
   La diferencia entre los dos tiempos es la latencia de extremo a extremo.
4. Repetir 5 veces. Guardar en `app/mediciones/D2-extremo-a-extremo/`.

- [ ] Latencias: ______ ______ ______ ______ ______  → promedio ______ ms

### 4.2 Bajo carga — F6, D4

Tres corridas de `d1-latencia.sh` (cada una graba también segmentos para
contar cuadros):

    [placa] cd /root/scripts
    [placa] DIR=/tmp/f6-sin SEG=30 ./d1-latencia.sh

    # carga de CPU: un bucle ocupado por núcleo
    [placa] C=""; for i in 1 2 3 4; do sh -c 'while :; do :; done' & C="$C $!"; done
    [placa] DIR=/tmp/f6-cpu SEG=30 ./d1-latencia.sh; kill $C

    # carga de E/S a la microSD (la que de verdad compite con la grabación)
    [placa] dd if=/dev/zero of=/var/lib/acceso/lastre bs=1M count=1500 & D=$!
    [placa] DIR=/tmp/f6-es SEG=30 ./d1-latencia.sh; kill $D 2>/dev/null; rm -f /var/lib/acceso/lastre

    [PC]    for c in sin cpu es; do scp root@<IP>:/tmp/f6-$c/D1-resumen-rpi4.txt app/mediciones/F6-latencia-$c.txt; done

- [ ] Fuente → `tx` p99: sin carga ______  CPU ______  E/S ______ ms
- [ ] ¿La latencia bajo carga se acerca a lo que predice B3 (801 ms con las colas llenas)? ______

---

## 5. Reinicio y corte de energía — H6, H3 caso 3 (15 min)

    [placa] wc -l /var/lib/acceso/accesos.log      # antes: ______
    [placa] reboot

Al volver:

    [placa] systemctl is-active acceso-control
    [placa] wc -l /var/lib/acceso/accesos.log      # después: ______ (igual o mayor)
    [placa] python3 -c "import json; [json.loads(l) for l in open('/var/lib/acceso/accesos.log')]; print('todas las lineas son JSON valido')"
    [placa] tail -3 /var/lib/acceso/accesos.log > /tmp/H6-tras-reinicio.txt

Repetir **desenchufando** la alimentación 30 s en lugar de `reboot`
(H3 caso 3), escuchando el buzzer durante el corte.

- [ ] Tras `reboot`: servicio activo, bitácora intacta, JSON válido
- [ ] Tras el corte: servicio activo, bitácora intacta
- [ ] Buzzer en silencio durante el corte y el arranque
- [ ] `verificar_corruptos` al arrancar tras el corte: ______ borrados

---

## 6. Recolección y análisis en la PC (10 min)

Antes, con la cámara **tapada o con poca luz** durante 2 minutos, para A3:

    [PC] ./app/scripts/vigilancia.py --ip <IP>     # comando RECOLECTAR
    [PC] ./app/scripts/analizar-segmentos.sh ~/recoleccion/evidencia "poca luz" > app/mediciones/A3-fps-poca-luz.txt
    [PC] for f in B4-memoria-rpi4 B5-callbacks-rpi4 E4-cierre-corregido B6-clip-al-detener \
             E2-desconexion H2-clasificador-colgado E5-disco-lleno H6-tras-reinicio; do
             scp root@<IP>:/tmp/$f.txt app/mediciones/; done

- [ ] A3 con poca luz: ______ fps

---

## Opcional, si sobra tiempo: `dmabuf` — C4 §3.3

Con el servicio detenido (10 s), 600 cuadros por cada variante, comparando el
tiempo de CPU (`user` + `sys`):

    [placa] systemctl stop acceso-control; sleep 10
    [placa] time gst-launch-1.0 -q v4l2src device=/dev/video0 num-buffers=600 \
              ! image/jpeg,width=1280,height=720,framerate=30/1 \
              ! v4l2jpegdec ! v4l2convert ! v4l2h264enc ! 'video/x-h264,level=(string)4' ! fakesink
    [placa] time gst-launch-1.0 -q v4l2src device=/dev/video0 num-buffers=600 \
              ! image/jpeg,width=1280,height=720,framerate=30/1 \
              ! v4l2jpegdec capture-io-mode=dmabuf \
              ! v4l2convert output-io-mode=dmabuf-import capture-io-mode=dmabuf \
              ! v4l2h264enc output-io-mode=dmabuf-import ! 'video/x-h264,level=(string)4' ! fakesink
    [placa] systemctl start acceso-control

- [ ] mmap: user+sys ______ s   dmabuf: user+sys ______ s  (o: falla con ______)

---

## Resumen de lo que queda en el repo

| Archivo en `app/mediciones/` | Ítems |
|---|---|
| `A1-A6-grafo-rpi4.txt` (+ `app/grafos/acceso-rpi4.dot`, `.svg`) | A1, A2, A5, A6, B1, B3 |
| `D1-resumen-rpi4.txt` | D1, D4, B5 (con tracer) |
| `G1-plugins.txt` | G1 |
| `B4-memoria-rpi4.txt` | B4 |
| `B5-callbacks-rpi4.txt` | B5, C4 §3.1 |
| `E4-cierre-corregido.txt` | E4 |
| `B6-clip-al-detener.txt` | B6 |
| `E2-desconexion.txt` | E2, H3 caso 1 |
| `H2-clasificador-colgado.txt` | H2, H1 |
| `E5-disco-lleno.txt` | E5 |
| `D2-extremo-a-extremo/` | D2 |
| `F6-latencia-{sin,cpu,es}.txt` | F6, D4 |
| `H6-tras-reinicio.txt` | H6, H3 caso 3 |
| `A3-fps-poca-luz.txt` | A3 |
| Notas de 3.3 en la bitácora | H3 caso 2 |
