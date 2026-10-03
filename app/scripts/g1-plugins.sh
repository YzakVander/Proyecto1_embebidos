#!/bin/sh
# G1 - deriva que plugin, biblioteca y subpaquete de Yocto aporta cada
# elemento de la tuberia. La lista NO se adivina: se saca de la tuberia
# real (pipeline.py + acceso.conf) y de gst-inspect-1.0.
#
# El subpaquete se DERIVA con la convencion de las recetas de GStreamer en
# Yocto: gstreamer1.0-<conjunto>-<plugin> (p. ej. gst-plugins-good +
# video4linux2 -> gstreamer1.0-plugins-good-video4linux2). Los elementos del
# nucleo (tee, queue, capsfilter, filesink) vienen en el paquete gstreamer1.0.
# La convencion no siempre aplica: en wrynose gstreamer1.0-plugins-ugly no
# se divide por plugin (todo queda en ese paquete; verificado por el Rol B,
# bitbake falla con Nothing RPROVIDES para -ugly-x264). Ese caso se detecta;
# para cualquier otro, verificar en el host de compilacion con
#     oe-pkgdata-util find-path */<biblioteca>
# Contrastar contra packagegroup-acceso.bb.
#
# Uso, en la placa o en la PC:  ./g1-plugins.sh
# En la placa, si los v4l2* salen "no disponible", detener primero el
# servicio: el bloque bcm2835-codec no admite otro proceso mientras
# acceso-control lo usa (C1-hallazgo-contextos.txt).
set -u

# Elementos que instancia la tuberia real (ver --mostrar-tuberia y el .dot de A6)
TUBERIA="v4l2src v4l2jpegdec v4l2convert v4l2h264enc h264parse tee queue capsfilter
splitmuxsink mp4mux filesink rtph264pay udpsink appsink"
# Solo para diagnostico y para la comparacion de C2: no los usa la aplicacion
DIAGNOSTICO="videotestsrc x264enc"

campo() {   # campo <elemento> <Name|Filename|Source module>
    gst-inspect-1.0 "$1" 2>/dev/null | sed -n "s/^ *$2  *//p" | head -1
}

listar() {
    for e in $1; do
        plugin=$(campo "$e" Name)
        if [ -z "$plugin" ]; then
            printf '%-14s %s\n' "$e" "(no disponible en este sistema)"
            continue
        fi
        lib=$(basename "$(campo "$e" Filename)")
        modulo=$(campo "$e" "Source module")
        if [ "$modulo" = "gstreamer" ]; then
            paquete="gstreamer1.0"
        elif [ "$modulo" = "gst-plugins-ugly" ]; then
            paquete="gstreamer1.0-plugins-ugly (no se divide por plugin)"
        else
            paquete="gstreamer1.0-${modulo#gst-}-$plugin"
        fi
        printf '%-14s %-18s %-28s %s\n' "$e" "$plugin" "$lib" "$paquete"
    done
}

echo "# G1 - $(uname -n) | $(gst-inspect-1.0 --version 2>/dev/null | sed -n 2p)"
if command -v systemctl >/dev/null 2>&1 &&
   systemctl is-active --quiet acceso-control 2>/dev/null; then
    echo "# AVISO: acceso-control esta corriendo; si los v4l2* salen 'no disponible',"
    echo "#        detenerlo (systemctl stop acceso-control) y repetir"
fi
printf '%-14s %-18s %-28s %s\n' "ELEMENTO" "PLUGIN" "BIBLIOTECA" "SUBPAQUETE (derivado)"
echo "--- tuberia ---"
listar "$TUBERIA"
echo "--- diagnostico / C2 ---"
listar "$DIAGNOSTICO"
echo
echo "# SUBPAQUETE se deriva por convencion (gstreamer1.0-<conjunto>-<plugin>) y no"
echo "# siempre aplica: verificar con 'oe-pkgdata-util find-path */<biblioteca>'."
