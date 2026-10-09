# D1 del acta: medir la latencia de la tuberia con GST_TRACERS="latency" en la
# plataforma real. Sin esto, gst-inspect-1.0 responde "No such element or
# plugin 'coretracers'" y el tracer no produce ninguna muestra.
#
# tracer-hooks compila los puntos de enganche DENTRO de libgstreamer. Va en las
# dos imagenes a proposito: asi la biblioteca de la imagen de entrega y la de
# desarrollo son la misma, y la latencia medida en dev describe a las dos.
# Con GST_TRACERS sin definir -- que es el caso del servicio -- el costo es una
# comprobacion por evento.
#
# coretracers produce libgstcoretracers.so (latency, stats, rusage, leaks). Es
# una herramienta de diagnostico: se compila aqui, pero el PAQUETE solo se
# instala en la imagen de desarrollo, via packagegroup-acceso-diagnostico (G2).
PACKAGECONFIG:append = " tracer-hooks coretracers"

# El plugin de tracers es una herramienta de diagnostico: se separa en su
# propio paquete para que entre solo en la imagen de desarrollo (G2), igual
# que v4l-utils y x264enc. Sin esto cae en el paquete gstreamer1.0, que la
# imagen de entrega necesita, y viajaria en las dos.
# El =+ es obligatorio: el reparto de archivos sigue el orden de PACKAGES, y
# si este fuera despues de ${PN} el paquete principal se queda con el .so.
PACKAGES =+ "${PN}-tracers"
FILES:${PN}-tracers = "${libdir}/gstreamer-1.0/libgstcoretracers.so"
RDEPENDS:${PN}-tracers = "${PN}"
