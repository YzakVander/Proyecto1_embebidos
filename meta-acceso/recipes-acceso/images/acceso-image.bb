SUMMARY = "Imagen a la medida para el sistema de control de acceso"
LICENSE = "MIT"

inherit core-image

# SSH es lo que permite iterar el codigo Python sin regenerar la imagen:
# scp de los modulos + systemctl restart. Sin esto cada cambio costaria
# una compilacion completa.
IMAGE_FEATURES += "ssh-server-dropbear"

# Estas tres features dejan root sin contrasena y permiten login remoto.
# PROHIBIDO en la imagen de entrega (G2). Comentar antes de la version final.
IMAGE_FEATURES += "allow-empty-password allow-root-login empty-root-password"

IMAGE_INSTALL:append = "\
    packagegroup-acceso \
    packagegroup-acceso-diagnostico \
    acceso-control \
    python3-opencv \
    kernel-modules \
"

# Espacio para la evidencia en video
IMAGE_ROOTFS_EXTRA_SPACE = "1048576"

export IMAGE_BASENAME = "acceso-image"

# Estado seguro del GPIO de la bocina desde el arranque del kernel, antes de
# que inicie cualquier aplicacion. Sin esto, la linea podria quedar en alto
# al energizar y la bocina sonaria de forma continua.
RPI_EXTRA_CONFIG = "gpio=18=op,dl"
