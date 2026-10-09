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

RDEPENDS:${PN} = "wpa-supplicant systemd tzdata-americas"

do_install() {
    install -d ${D}${sysconfdir}/wpa_supplicant
    # 0600: el archivo lleva la contrasena de la red en claro
    install -m 0600 ${UNPACKDIR}/wpa_supplicant-wlan0.conf \
        ${D}${sysconfdir}/wpa_supplicant/wpa_supplicant-wlan0.conf

    install -d ${D}${sysconfdir}/systemd/network
    install -m 0644 ${UNPACKDIR}/25-wlan.network \
        ${D}${sysconfdir}/systemd/network/25-wlan.network

    # Zona horaria: DEFAULT_TIMEZONE no crea el enlace cuando se instala el
    # subpaquete tzdata-americas suelto, y sin /etc/localtime el sistema queda
    # en UTC. El sello del video saldria 6 h adelantado.
    install -d ${D}${sysconfdir}
    ln -sf ../usr/share/zoneinfo/America/Costa_Rica ${D}${sysconfdir}/localtime
    echo "America/Costa_Rica" > ${D}${sysconfdir}/timezone

    install -d ${D}${systemd_system_unitdir}/multi-user.target.wants
    ln -sf ${systemd_system_unitdir}/wpa_supplicant@.service \
        ${D}${systemd_system_unitdir}/multi-user.target.wants/wpa_supplicant@wlan0.service

    # systemd-networkd-wait-online espera por omision a que TODAS las
    # interfaces gestionadas esten configuradas. Con eth0 desconectada se
    # queda esperando hasta agotar el plazo (~2 min) y retrasa por igual a
    # network-online.target y a acceso-control, que lo pide con Wants. --any
    # lo deja seguir en cuanto UNA interfaz tiene direccion, que es lo que
    # corresponde en una placa que normalmente solo usa wlan0.
    #
    # Va como drop-in y no editando la unidad: la unidad pertenece al paquete
    # systemd y no se toca desde aqui. El ExecStart vacio es obligatorio,
    # systemd exige limpiar la lista antes de redefinirla.
    install -d ${D}${systemd_system_unitdir}/systemd-networkd-wait-online.service.d
    cat > ${D}${systemd_system_unitdir}/systemd-networkd-wait-online.service.d/10-any.conf <<EOF
[Service]
ExecStart=
ExecStart=${systemd_unitdir}/systemd-networkd-wait-online --any --timeout=30
EOF
}

FILES:${PN} = "\
    ${sysconfdir}/localtime \
    ${sysconfdir}/timezone \
    ${sysconfdir}/wpa_supplicant \
    ${sysconfdir}/systemd/network \
    ${systemd_system_unitdir}/multi-user.target.wants \
    ${systemd_system_unitdir}/systemd-networkd-wait-online.service.d \
"

CONFFILES:${PN} = "${sysconfdir}/wpa_supplicant/wpa_supplicant-wlan0.conf"
