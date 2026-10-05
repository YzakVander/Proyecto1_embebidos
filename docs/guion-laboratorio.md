# Guion de verificación en la Raspberry Pi 4

Primer arranque e inventario de la plataforma. Las mediciones del Rol A
(grafo, latencia, fallas) están en `guion-placa-rol-a.md`; la generación e
instalación de la imagen, en `tutorial-imagen-yocto.html`.

Fecha: ______  Hora inicio: ______  Hora fin: ______

> **Usar la imagen de desarrollo (`acceso-image-dev`).** Este guion entra por
> SSH como root sin contraseña y usa `v4l-utils`, `videotestsrc`, `x264enc` y
> `vcgencmd`, que solo vienen en esa imagen. La imagen de entrega
> (`acceso-image`) no los trae (G2).

## 0. Grabar la microSD

    lsblk -d -o NAME,SIZE,TYPE,TRAN     # identificar el dispositivo (~29 GB, TRAN=usb)
    sudo umount /dev/sdX?*
    sudo bmaptool copy --bmap acceso-image-dev-raspberrypi4-64.rootfs.wic.bmap \
        acceso-image-dev-raspberrypi4-64.rootfs.wic.bz2 /dev/sdX
    sync

Si la máquina del laboratorio es Windows: balenaEtcher, lee el .bz2 directo.

## 1. Primer arranque

Conectar HDMI, teclado, red, alimentación. Usuario: root, sin contraseña.

- [ ] Llega al prompt de login
- [ ] Tiempo de arranque: ______ s
- [ ] IP obtenida: ______________   (comando: `ip -4 addr show`)

## 2. Acceso remoto

Desde la laptop:  `ssh root@<IP>`

- [ ] SSH funciona

## 3. Inventario de plataforma (G5)

    uname -a
    cat /etc/os-release
    gst-inspect-1.0 --version
    python3 --version

- [ ] Kernel: ______  GStreamer: ______  Python: ______
      (esperado: 6.18.33-v8, 1.28.5, 3.14.x)

## 4. C1 — ¿el codificador por hardware existe de verdad?

    v4l2-ctl --list-devices
    ls -l /dev/video*
    v4l2-ctl -d /dev/video11 --list-ctrls | head -20

- [ ] /dev/video11 presente: SÍ / NO
- [ ] Controles del codificador visibles: SÍ / NO

## 5. Elementos de GStreamer (G3)

    rm -rf ~/.cache/gstreamer-1.0
    for e in v4l2src v4l2jpegdec v4l2convert v4l2h264enc h264parse tee queue \
             splitmuxsink mp4mux rtph264pay udpsink appsink; do
      printf '%-16s ' "$e"; gst-inspect-1.0 $e >/dev/null 2>&1 && echo OK || echo FALTA
    done

- [ ] Todos OK · faltantes: ______________

## 6. Python: el punto que más traba

    python3 -c "import gi; gi.require_version('Gst','1.0'); from gi.repository import Gst; Gst.init(None); print('Gst', Gst.version_string())"
    python3 -c "import cv2; print('OpenCV', cv2.__version__)"
    python3 -c "import numpy; print('NumPy', numpy.__version__)"

- [ ] Los tres importan sin error

## 7. Cámara USB real

> **Detener antes el servicio.** El bloque `bcm2835-codec` no admite un
> segundo proceso: con `acceso-control` corriendo, cualquier `gst-launch` con
> elementos `v4l2*` falla con `ret -3` (`C1-hallazgo-contextos.txt`).

    systemctl stop acceso-control && sleep 10
    v4l2-ctl --list-devices
    v4l2-ctl -d /dev/video0 --list-formats-ext | head -40

- [ ] Nodo: ______  Formato: ______  Resolución máxima en MJPEG: ______

Captura básica, con la misma cadena por hardware que usa la aplicación:

    gst-launch-1.0 -v v4l2src device=/dev/video0 num-buffers=60 \
      ! image/jpeg,width=1280,height=720,framerate=30/1 \
      ! v4l2jpegdec ! v4l2convert ! fakesink

- [ ] Captura OK

## 8. C2 — razón de CPU hardware vs software

Con el servicio todavía detenido.

    # software (x264enc: solo en la imagen de desarrollo)
    gst-launch-1.0 videotestsrc ! video/x-raw,format=I420,width=1280,height=720,framerate=30/1 ! x264enc tune=zerolatency bitrate=2500 ! fakesink &
    top -b -n 12 -d 5 -p $! | grep gst-launch

- [ ] CPU software: ______ %

    # hardware
    gst-launch-1.0 videotestsrc ! video/x-raw,format=NV12,width=1280,height=720,framerate=30/1 ! v4l2h264enc extra-controls=controls,video_bitrate=2500000 ! fakesink &
    top -b -n 12 -d 5 -p $! | grep gst-launch

- [ ] CPU hardware: ______ %
- [ ] Razón: ______ ×   (criterio: >= 5x)

Referencias: x86 solo software 174 % (`C2-software-x86.txt`); servicio
completo en la placa con la cadena por hardware 4.2 % (`C2-hardware-rpi4.txt`).

Al terminar: `systemctl start acceso-control`

## 9. F4 — throttling

    vcgencmd get_throttled     # esperado 0x0
    vcgencmd measure_temp

- [ ] get_throttled: ______  Temp: ______

## 10. H5 — buzzer: PWM disponible y silencio desde el arranque

El actuador es un buzzer pasivo en GPIO 18 (pin físico 12) por PWM de
hardware, no LEDs (`docs/H4-H5-actuacion-y-alcance.md`).

    ls /sys/class/pwm/                          # debe existir pwmchip0
    ls /boot/overlays/ | grep pwm               # pwm.dtbo presente
    grep -E "pwm|audio" /boot/config.txt        # dtoverlay=pwm,pin=18,func=2 y dtparam=audio=off

- [ ] `pwmchip0` presente y overlay cargado

Prueba del buzzer sin la aplicación (servicio detenido para que no compitan
por el canal):

    systemctl stop acceso-control
    ./probar-buzzer.sh                          # copiar antes app/scripts/probar-buzzer.sh
    systemctl start acceso-control

- [ ] Suenan el tono de permitido, los tres pitidos de denegado y el barrido
- [ ] Reinicio con el buzzer conectado: silencio entre el encendido y el arranque del servicio

## 11. E6 — reinicio automático

    systemctl status acceso-control
    journalctl -u acceso-control -n 30

- [ ] El servicio arrancó solo

    kill -9 $(systemctl show -p MainPID --value acceso-control)
    sleep 8 && systemctl status acceso-control

- [ ] Se reinició solo tras 5 s

> **Hallazgo conocido** (`E6-reinicio-rpi4.txt`): tras un `kill -9` el bloque
> de video queda inservible; el servicio aparece activo pero no graba
> (segmentos de pocos KB). Verificar con `ls -lh /var/lib/acceso/evidencia/`
> y, si pasa, reiniciar la placa con `reboot`.

## 12. Transmisión en vivo (CU-1)

No hay que configurar ninguna IP: al conectarse el puesto de vigilancia al
canal de comandos (TCP 5001), la placa redirige el video a esa computadora.

En la laptop, desde el repositorio:

    python3 app/scripts/puesto-vigilancia.py --ip <IP de la placa>
    # o, en consola:  python3 app/scripts/vigilancia.py --ip <IP de la placa>

- [ ] Video recibido desde la Pi
- [ ] El log de la placa muestra `destino de transmision: ... -> <IP de la laptop>:5000`

## 13. Casos de uso

Desde el puesto de vigilancia (botones o comandos), o en la placa por la FIFO:

    echo "SOLICITUD ID-001" > /tmp/acceso-eventos
    echo "PERMITIR"         > /tmp/acceso-eventos
    echo "SOLICITUD ID-002" > /tmp/acceso-eventos
    echo "DENEGAR"          > /tmp/acceso-eventos
    echo "SOLICITUD ID-003" > /tmp/acceso-eventos    # no responder, 30 s

    acceso-control --ver-bitacora
    ls -lh /var/lib/acceso/evidencia /var/lib/acceso/eventos

- [ ] Los tres resultados distintos en la bitácora
- [ ] Un clip MP4 por solicitud en `eventos/`
- [ ] El buzzer suena con el patrón de cada resultado

## 14. E2 — desconexión de cámara en caliente

Desconectar la webcam con el servicio corriendo.

    journalctl -u acceso-control -f

- [ ] Registra la alerta y reintenta cada 5 s
- [ ] Al reconectar, se recupera. Nodo al volver (`ls /dev/video*`): ______

## 15. E4 — cierre ordenado

    systemctl stop acceso-control
    journalctl -u acceso-control -n 15 | grep "segmento cerrado al detener"
    U=$(ls -t /var/lib/acceso/evidencia/*.mp4 | head -1)
    python3 -c "from acceso.retencion import es_mp4_sano; print('$U', es_mp4_sano('$U'))"
    systemctl start acceso-control

- [ ] El último segmento es reproducible (`True`)

## Qué llevar

- [ ] USB con la imagen de desarrollo (.wic.bz2 + .bmap)
- [ ] Webcam USB
- [ ] Buzzer pasivo + 2 cables dupont (GPIO 18 / pin 12 y GND / pin 14)
- [ ] Cable de red o celular como hotspot
- [ ] Laptop con GStreamer, `python3-tk` y `python3-opencv` (puesto de vigilancia)
- [ ] Este guion impreso
