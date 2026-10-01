SUMMARY = "Dependencias de tiempo de ejecucion del sistema de control de acceso"
DESCRIPTION = "Plugins de GStreamer declarados a nivel de SUBPAQUETE (G1), \
derivados de los elementos que la aplicacion usa realmente. No se instalan \
los conjuntos completos: cada uno agrega decenas de MiB y CVE potenciales."
LICENSE = "MIT"

inherit packagegroup

PACKAGES = "\
    ${PN} \
    ${PN}-gstreamer \
    ${PN}-python \
    ${PN}-io \
    ${PN}-diagnostico \
"

RDEPENDS:${PN} = "\
    ${PN}-gstreamer \
    ${PN}-python \
    ${PN}-io \
"

# --- GStreamer: solo los subpaquetes que aportan los elementos usados ---
# Trazabilidad elemento -> biblioteca -> subpaquete en
# app/mediciones/G1-plugins.txt
SUMMARY:${PN}-gstreamer = "Plugins de GStreamer estrictamente necesarios"
RDEPENDS:${PN}-gstreamer = "\
    gstreamer1.0 \
    gstreamer1.0-plugins-base-app \
    gstreamer1.0-plugins-base-videoconvertscale \
    gstreamer1.0-plugins-good-video4linux2 \
    gstreamer1.0-plugins-good-isomp4 \
    gstreamer1.0-plugins-good-rtp \
    gstreamer1.0-plugins-good-udp \
    gstreamer1.0-plugins-good-multifile \
    gstreamer1.0-plugins-good-jpeg \
    gstreamer1.0-plugins-bad-videoparsersbad \
"

# --- Python: pygobject NO basta sin los .typelib ---
SUMMARY:${PN}-python = "Interprete y enlaces de GObject/GStreamer"
RDEPENDS:${PN}-python = "\
    python3-core \
    python3-logging \
    python3-threading \
    python3-json \
    python3-datetime \
    python3-pygobject \
    gstreamer1.0-python \
"

# --- GPIO para los LED de estado ---
SUMMARY:${PN}-io = "Acceso a GPIO desde espacio de usuario"
RDEPENDS:${PN}-io = "\
    libgpiod \
    libgpiod-tools \
"

# --- Diagnostico: se excluye de la imagen de produccion (G2) ---
SUMMARY:${PN}-diagnostico = "Herramientas de prototipado y verificacion"
RDEPENDS:${PN}-diagnostico = "\
    gstreamer1.0-plugins-base-videotestsrc \
    v4l-utils \
"
