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
# 8 GiB para la evidencia. El tope de retencion de la aplicacion es de
# 6000 MiB, asi que la particion queda por encima: si fuera al reves el
# disco se llenaria antes de que la politica de retencion actuara, y el
# sistema dejaria de grabar sin que nada lo advirtiera.
# Medido: a 640x480 y 800 kbit/s un segmento de 60 s pesa ~6 MiB, de modo
# que 6000 MiB son unas 16 horas de grabacion continua.
IMAGE_ROOTFS_EXTRA_SPACE = "8388608"

export IMAGE_BASENAME = "acceso-image"

# PWM de hardware para el buzzer pasivo en GPIO 18 (pin fisico 12). El buzzer
# no oscila solo: necesita una onda cuadrada. Conmutar desde Python daria un
# tono irregular y consumiria CPU. dtparam=audio=off libera el PWM, que el
# audio analogico ocupa. Con el overlay cargado el pin arranca sin senal.
RPI_EXTRA_CONFIG = "dtoverlay=pwm,pin=18,func=2\ndtparam=audio=off"
