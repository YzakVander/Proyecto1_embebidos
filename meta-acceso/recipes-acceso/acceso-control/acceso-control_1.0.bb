SUMMARY = "Sistema de control de acceso basado en GStreamer"
DESCRIPTION = "Aplicacion en Python que captura video del punto de entrada, \
retiene evidencia en disco, transmite en vivo al puesto de vigilancia y \
conmuta los indicadores de estado ante un evento de identificacion."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

# ENTREGA PRELIMINAR: los fuentes viajan dentro de la capa.
# Para la entrega final migrar a git y fijar SRCREV (trazabilidad del SBOM):
#   SRC_URI = "git://<repo>;branch=main;protocol=https;subpath=app"
#   SRCREV  = "<sha1 completo>"
SRC_URI = "\
    file://acceso \
    file://acceso-control.service \
    file://acceso.conf \
"

# Desde Yocto 5.1 los archivos de SRC_URI se desempaquetan en ${UNPACKDIR},
# no en ${WORKDIR}. En ramas anteriores habria que sustituirlo.
S = "${UNPACKDIR}"

inherit systemd python3-dir

SYSTEMD_SERVICE:${PN} = "acceso-control.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

# Instalacion manual en lugar de setuptools3: el paquete son ocho modulos
# sin dependencias de compilacion. Un pyproject.toml agregaria
# python3-setuptools-native al build sin aportar nada.
do_install() {
    # Paquete Python
    install -d ${D}${PYTHON_SITEPACKAGES_DIR}/acceso
    install -m 0644 ${UNPACKDIR}/acceso/*.py ${D}${PYTHON_SITEPACKAGES_DIR}/acceso/

    # Ejecutable
    install -d ${D}${bindir}
    cat > ${D}${bindir}/acceso-control <<EOF
#!/bin/sh
exec ${bindir}/python3 -m acceso "\$@"
EOF
    chmod 0755 ${D}${bindir}/acceso-control

    # Configuracion
    install -d ${D}${sysconfdir}/acceso
    install -m 0644 ${UNPACKDIR}/acceso.conf ${D}${sysconfdir}/acceso/acceso.conf

    # Unidad de systemd
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${UNPACKDIR}/acceso-control.service ${D}${systemd_system_unitdir}/

    # Directorios de evidencia (systemd tambien crea /var/lib/acceso
    # via StateDirectory, pero se declaran para que existan desde la imagen)
    install -d ${D}${localstatedir}/lib/acceso/evidencia
    install -d ${D}${localstatedir}/lib/acceso/eventos
}

FILES:${PN} += "\
    ${PYTHON_SITEPACKAGES_DIR}/acceso \
    ${systemd_system_unitdir} \
    ${localstatedir}/lib/acceso \
"

CONFFILES:${PN} = "${sysconfdir}/acceso/acceso.conf"

RDEPENDS:${PN} = "packagegroup-acceso"
