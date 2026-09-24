SUMMARY = "Imagen a la medida para el sistema de control de acceso"
LICENSE = "MIT"

inherit core-image

# SSH es lo que permite iterar el codigo Python sin regenerar la imagen:
# scp de los modulos + systemctl restart. Sin esto cada cambio costaria
# una compilacion completa.
IMAGE_FEATURES += "ssh-server-dropbear"

# debug-tweaks deja root sin contrasena. Necesario para desarrollar,
# PROHIBIDO en la imagen de entrega (G2). Comentar antes de la version final.
IMAGE_FEATURES += "debug-tweaks"

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
