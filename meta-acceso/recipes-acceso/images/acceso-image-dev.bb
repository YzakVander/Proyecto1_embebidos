SUMMARY = "Imagen de DESARROLLO del sistema de control de acceso"
DESCRIPTION = "Hereda de acceso-image y agrega las concesiones que la imagen \
de entrega no puede llevar (G2): root sin contrasena, login remoto y las \
herramientas de prototipado y medicion (v4l-utils, videotestsrc, x264enc)."

require acceso-image.bb

# Solo en desarrollo: permiten iterar por SSH sin regenerar la imagen.
IMAGE_FEATURES += "allow-empty-password allow-root-login empty-root-password"

# Herramientas de medicion. x264enc es el termino de comparacion por software
# del item C2; no forma parte de la tuberia de produccion, que usa v4l2h264enc.
IMAGE_INSTALL:append = " packagegroup-acceso-diagnostico"

export IMAGE_BASENAME = "acceso-image-dev"
