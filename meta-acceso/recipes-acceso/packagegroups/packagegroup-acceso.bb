SUMMARY = "Dependendicas de tiempo de ejecucion del sistema de control de acceso"
LICENSE = "MIT"

inherit packagegroup

RDEPENDS:${PN} = "\
    v4l-utils \
    gstreamer1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    python3-core \
    python3-pygobject \
    gstreamer1.0-python \
    libgpiod \
    libgpiod-tools \
"
