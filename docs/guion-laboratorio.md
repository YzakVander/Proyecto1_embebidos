# Guion de verificación en la Raspberry Pi 4

Fecha: ______  Hora inicio: ______  Hora fin: ______

## 0. Grabar la microSD

    lsblk -d -o NAME,SIZE,TYPE,TRAN     # identificar el dispositivo (~29 GB, TRAN=usb)
    sudo umount /dev/sdX*
    sudo bmaptool copy --bmap acceso-image-...wic.bmap acceso-image-...wic.bz2 /dev/sdX
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

## 3. Inventario de plataforma

    uname -a
    cat /etc/os-release
    gst-inspect-1.0 --version
    python3 --version

- [ ] Kernel: ______  GStreamer: ______  Python: ______

## 4. C1 — ¿el codificador por hardware existe de verdad?

    v4l2-ctl --list-devices
    ls -l /dev/video*
    v4l2-ctl -d /dev/video11 --list-ctrls | head -20

- [ ] /dev/video11 presente: SÍ / NO
- [ ] Controles del codificador visibles: SÍ / NO

## 5. Elementos de GStreamer

    for e in v4l2src v4l2h264enc v4l2convert h264parse splitmuxsink rtph264pay udpsink appsink jpegdec videoconvert; do
      printf '%-16s ' "$e"; gst-inspect-1.0 $e >/dev/null 2>&1 && echo OK || echo FALTA
    done

- [ ] Todos OK · faltantes: ______________

## 6. Python: el punto que más traba

    python3 -c "import gi; gi.require_version('Gst','1.0'); from gi.repository import Gst; Gst.init(None); print('Gst', Gst.version_string())"
    python3 -c "import cv2; print('OpenCV', cv2.__version__)"
    python3 -c "import numpy; print('NumPy', numpy.__version__)"

- [ ] Los tres importan sin error

## 7. Cámara USB real

Conectar la webcam.

    v4l2-ctl --list-devices
    v4l2-ctl -d /dev/video0 --list-formats-ext | head -20

- [ ] Nodo: ______  Formato: ______  Resolución: ______

Captura básica:

    gst-launch-1.0 -v v4l2src device=/dev/videoN num-buffers=60 ! image/jpeg,width=1280,height=720,framerate=30/1 ! jpegdec ! videoconvert ! fakesink

- [ ] Captura OK

## 8. C2 — razón de CPU hardware vs software

    # software
    gst-launch-1.0 videotestsrc ! video/x-raw,format=I420,width=1280,height=720,framerate=30/1 ! x264enc tune=zerolatency bitrate=2500 ! fakesink &
    top -b -n 12 -d 5 -p $! | grep gst-launch

- [ ] CPU software: ______ %

    # hardware
    gst-launch-1.0 videotestsrc ! video/x-raw,format=NV12,width=1280,height=720,framerate=30/1 ! v4l2h264enc extra-controls=controls,video_bitrate=2500000 ! fakesink &
    top -b -n 12 -d 5 -p $! | grep gst-launch

- [ ] CPU hardware: ______ %
- [ ] Razón: ______ ×   (criterio: >= 5x)

Referencia x86 solo software: 174 %.

## 9. F4 — throttling

    vcgencmd get_throttled     # esperado 0x0
    vcgencmd measure_temp

- [ ] get_throttled: ______  Temp: ______

## 10. H5 — estado de los GPIO al arranque

    gpiodetect
    gpioget gpiochip0 27 22
    grep gpio /boot/config.txt

- [ ] GPIO 27 y 22 en estado bajo desde el arranque

LED: ánodo a GPIO por resistencia de 330 ohm, cátodo a GND.

    gpioset --mode=time --sec=3 gpiochip0 27=1    # verde
    gpioset --mode=time --sec=3 gpiochip0 22=1    # rojo

- [ ] Ambos LED encienden

## 11. E6 — reinicio automático

    systemctl status acceso-control
    journalctl -u acceso-control -n 30

- [ ] El servicio arrancó solo

    kill -9 $(systemctl show -p MainPID --value acceso-control)
    sleep 8 && systemctl status acceso-control

- [ ] Se reinició solo tras 5 s

## 12. Transmisión en vivo (CU-1)

Editar `/etc/acceso/acceso.conf`: `[streaming] host = <IP de la laptop>`

    systemctl restart acceso-control

En la laptop:

    gst-launch-1.0 -v udpsrc port=5000 caps="application/x-rtp,media=(string)video,clock-rate=(int)90000,encoding-name=(string)H264,payload=(int)96" ! rtpjitterbuffer latency=100 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink sync=false

- [ ] Video recibido desde la Pi

## 13. Casos de uso

    echo "SOLICITUD ID-001" > /run/acceso/eventos
    echo "PERMITIR"         > /run/acceso/eventos
    echo "SOLICITUD ID-002" > /run/acceso/eventos
    echo "DENEGAR"          > /run/acceso/eventos
    echo "SOLICITUD ID-003" > /run/acceso/eventos    # no responder, 30 s

    acceso-control --ver-bitacora
    ls -lh /var/lib/acceso/evidencia /var/lib/acceso/eventos

- [ ] Los tres resultados distintos en la bitácora

## 14. E2 — desconexión de cámara en caliente

Desconectar la webcam con el servicio corriendo.

    journalctl -u acceso-control -f

- [ ] Registra la alerta y reintenta
- [ ] Al reconectar, se recupera

## 15. E4 — cierre ordenado

    systemctl stop acceso-control
    # copiar el último MP4 a la laptop y verificar
    ffprobe <último>.mp4

- [ ] El último segmento es reproducible

## Qué llevar

- [ ] USB con la imagen (.wic.bz2 + .bmap)
- [ ] Webcam USB
- [ ] 2 LED + 2 resistencias de 330 ohm + cables dupont
- [ ] Cable de red o celular como hotspot
- [ ] Este guion impreso
