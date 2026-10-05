SUMMARY = "Configuracion de red inalambrica del sistema de control de acceso"
DESCRIPTION = "Deja la placa conectandose sola a las redes conocidas al \
arrancar. Sin esto hay que editar /etc/wpa_supplicant/ a mano en la microSD \
despues de cada grabado, y la configuracion se pierde al regenerar la imagen."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "\
    file://wpa_supplicant-wlan0.conf \
    file://25-wlan.network \
"

inherit allarch

# NO se usa SYSTEMD_SERVICE: esa variable exige que la unidad la instale ESTA
# receta, y wpa_supplicant@.service pertenece al paquete wpa-supplicant. El
# enlace de activacion se crea a mano en do_install, que es lo mismo que hace
# systemctl enable.
#
# La unidad parametrizada lee /etc/wpa_supplicant/wpa_supplicant-%I.conf,
# donde %I es el nombre de la interfaz: de ahi el nombre del archivo.

RDEPENDS:${PN} = "wpa-supplicant systemd"

do_install() {
    install -d ${D}${sysconfdir}/wpa_supplicant
    # 0600: el archivo lleva la contrasena de la red en claro
    install -m 0600 ${UNPACKDIR}/wpa_supplicant-wlan0.conf \
        ${D}${sysconfdir}/wpa_supplicant/wpa_supplicant-wlan0.conf

    install -d ${D}${sysconfdir}/systemd/network
    install -m 0644 ${UNPACKDIR}/25-wlan.network \
        ${D}${sysconfdir}/systemd/network/25-wlan.network

    install -d ${D}${systemd_system_unitdir}/multi-user.target.wants
    ln -sf ${systemd_system_unitdir}/wpa_supplicant@.service \
        ${D}${systemd_system_unitdir}/multi-user.target.wants/wpa_supplicant@wlan0.service
}

FILES:${PN} = "\
    ${sysconfdir}/wpa_supplicant \
    ${sysconfdir}/systemd/network \
    ${systemd_system_unitdir}/multi-user.target.wants \
"

CONFFILES:${PN} = "${sysconfdir}/wpa_supplicant/wpa_supplicant-wlan0.conf"
