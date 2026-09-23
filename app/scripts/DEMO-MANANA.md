# Guion de demostración — transmisión en vivo entre dos computadoras

## Antes de empezar

1. Activar hotspot del celular. AMBOS se conectan a él.
2. Cada uno abre CMD en Windows y corre:  ipconfig
   Anotar la "Dirección IPv4" del adaptador Wi-Fi.

   Mi IP:  _______________
   IP del compañero: _______________

3. Prueba de alcance, desde mi WSL2:
       ping -c 4 <IP del compañero>

   Si NO responde:
     - Firewall de Windows en SU máquina: permitir red privada
     - Confirmar que ambos están en el hotspot, no en otro WiFi

## Receptor (computadora del compañero)

Necesita GStreamer instalado. Corre:

    gst-launch-1.0 -v udpsrc port=5000 \
      caps="application/x-rtp,media=(string)video,clock-rate=(int)90000,encoding-name=(string)H264,payload=(int)96" \
      ! rtpjitterbuffer latency=100 \
      ! rtph264depay ! h264parse ! avdec_h264 \
      ! videoconvert ! autovideosink sync=false

Windows preguntará si permite la conexión: SÍ, en redes privadas.

## Emisor (mi máquina)

1. Editar la IP de destino:
       nano config/acceso.conf
       [streaming] host = <IP del compañero>

2. Levantar el servicio:
       python3 -m acceso -c config/acceso.conf

3. Desde otra terminal, los casos de uso:
       echo "SOLICITUD ID-001" > /tmp/acceso-eventos
       echo "PERMITIR"         > /tmp/acceso-eventos

       echo "SOLICITUD ID-002" > /tmp/acceso-eventos
       echo "DENEGAR"          > /tmp/acceso-eventos

       echo "SOLICITUD ID-003" > /tmp/acceso-eventos
       (no responder — a los 30 s deniega por vencimiento)

4. Mostrar la bitácora:
       python3 -m acceso -c config/acceso.conf --ver-bitacora

## PLAN B — si la red no funciona

Correr emisor y receptor en MI máquina con host=127.0.0.1.
Demuestra la arquitectura completa; lo único que no se prueba es el
salto entre máquinas. Declararlo abiertamente.

## PLAN C — si falla la aplicación

gst-launch suelto, emisor y receptor. La tubería está verificada.
