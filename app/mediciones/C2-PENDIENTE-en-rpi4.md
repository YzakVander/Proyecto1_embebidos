# C2 - comandos a ejecutar SOBRE LA RASPBERRY PI 4

Requiere: imagen de Yocto arrancada, v4l-utils y GStreamer instalados.

    # C1 - confirmar que el codificador por hardware existe de verdad
    v4l2-ctl --list-devices
    v4l2-ctl -d /dev/video11 --list-ctrls

    # C2 - las dos mitades, MISMO equipo, misma resolucion y tasa
    ./medir-cpu.sh software-rpi4
    ./medir-cpu.sh hardware-rpi4 "v4l2h264enc extra-controls=controls,video_bitrate=2500000"

    # F4 - throttling termico
    vcgencmd get_throttled    # debe dar 0x0
    vcgencmd measure_temp

Criterio de C2: la ruta por hardware debe ser >= 5x mas barata.
Referencia x86 (WSL2, solo software): 174% CPU a 1280x720@30.
