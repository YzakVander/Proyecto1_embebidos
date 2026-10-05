# H4 / H5 — Actuación: alcance, estado seguro y riesgo de atrapamiento

## 1. Alcance real del actuador

El sistema **no** acciona una cerradura eléctrica. El actuador es un **buzzer
pasivo en GPIO 18 (pin físico 12)**, manejado por el generador PWM de hardware
del BCM2711 a través de sysfs (`/sys/class/pwm/pwmchip0/pwm0`).

El buzzer indica el resultado de la decisión de acceso:

| Resultado | Patrón |
|---|---|
| PERMITIDO | tono continuo de 2500 Hz durante 800 ms |
| DENEGADO | 3 pitidos de 800 Hz, 200 ms cada uno, pausas de 150 ms |
| VENCIDO | idéntico a DENEGADO: para el sujeto es una negación (CU-5) |

### Por qué PWM de hardware y no conmutación por software

El buzzer es pasivo: no oscila por sí solo, necesita una onda cuadrada a la
frecuencia del tono. Conmutar un pin desde Python cada 200 µs (2.5 kHz) daría
un tono irregular y consumiría CPU que necesitan GStreamer y el codificador.
El generador PWM produce la onda sin intervención del procesador: Python solo
escribe `period`, `duty_cycle` y `enable`.

## 2. H5 — Estado definido desde el arranque

El ítem del acta pide `gpio=<n>=op,dl` en `config.txt`. **Ese parámetro no
aplica aquí** y ponerlo sería incorrecto: el pin 18 lo toma el overlay de PWM
(`dtoverlay=pwm,pin=18,func=2`), no el driver de GPIO, y declararlo como
salida simple entraría en conflicto con el overlay.

Lo que se garantiza es lo equivalente, que es lo que el ítem busca de fondo:
**con el overlay cargado el canal PWM arranca sin señal**, de modo que el
buzzer está en silencio desde el firmware, antes de que exista el proceso
Python. `TonoPWM.__init__` además llama a `silencio()` al construirse, y
`cerrar()` lo deja en silencio al salir.

### Hallazgo de plataforma

`meta-raspberrypi` declara `RPI_KERNEL_DEVICETREE_OVERLAYS` como una lista
**explícita** de overlays a desplegar, y `pwm.dtbo` no está en ella: el archivo
existe en los `rpi-bootfiles` del firmware pero nunca llega a `/boot/overlays/`.
Sin esto el firmware ignora el `dtoverlay=pwm` de `config.txt` **en silencio** y
`/sys/class/pwm/` queda vacío. La corrección está en `local.conf.sample`:

    RPI_KERNEL_DEVICETREE_OVERLAYS:append = " overlays/pwm.dtbo overlays/pwm-2chan.dtbo"

## 3. H4 — Botón de salida: fuera de alcance, con justificación

El acta asume un sistema con cerradura eléctrica y pide que el botón de salida
la libere **por hardware**, sin pasar por el GPIO ni por el software. Este
proyecto no tiene cerradura ni botón de salida, así que el ítem **se declara
fuera de alcance**.

### Por qué ese botón existe, y por qué no se puede omitir si hubiera cerradura

Una puerta controlada por software crea un **riesgo de atrapamiento**: si el
proceso muere, el Pi se cuelga o se corta la energía, las personas que están
dentro quedan encerradas. Por eso la liberación de emergencia nunca puede
depender del mismo elemento que toma la decisión de acceso.

### Diseño que se exigiría con una cerradura real

1. Cerradura con comportamiento de falla seguro acorde al uso (en vías de
   evacuación, que libere al perder alimentación).
2. Botón de salida **en serie con la alimentación de la cerradura**, no
   conectado a una entrada del Pi. Al pulsarlo corta la energía del electroimán
   aunque el software esté caído.
3. El GPIO del Pi solo puede **energizar** la cerradura, nunca ser la única vía
   de liberación.
4. Verificación: desconectar el Pi en caliente y comprobar que el botón sigue
   abriendo la puerta.

## 4. Diagrama eléctrico del actuador actual

    BCM2711 (Raspberry Pi 4)
    ┌──────────────────┐
    │  GPIO 18         │──────────┐
    │  (pin físico 12) │          │
    │                  │        ┌─┴─┐
    │  GND             │        │   │  Buzzer pasivo
    │  (pin físico 14) │────┐   │   │
    └──────────────────┘    │   └─┬─┘
                            └─────┘

    PWM0 → GPIO 18 vía dtoverlay=pwm,pin=18,func=2
    dtparam=audio=off libera el PWM, que el audio analógico ocupa.

**No hay cerradura, relé, ni botón de salida en el montaje.**

## 5. Verificación realizada

- [x] Reinicio con el buzzer conectado: no emite sonido entre el encendido y
      el arranque del servicio
- [x] `/boot/overlays/pwm.dtbo` presente tras el build
- [x] `/sys/class/pwm/pwmchip0/` existe y el canal arranca sin exportar
- [x] Al detener el servicio el buzzer queda en silencio
