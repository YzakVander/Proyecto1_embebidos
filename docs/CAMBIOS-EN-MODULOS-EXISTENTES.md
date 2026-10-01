# Cambios en los módulos existentes

Tres archivos ya existentes hay que tocar. Abajo va **exactamente** qué
agregar y dónde, sobre la versión actual del repositorio.

---

## 1. `config.py`

### 1.1 Dos dataclasses nuevos

Pegar **antes** de `@dataclass class Config:`

```python
@dataclass
class QrCfg:
    """CU-13: lectura de credenciales QR con OpenCV."""
    habilitado: bool = True
    # Resolución del appsink de cuadros crudos. 640x480 medido: 15 ms por
    # análisis en x86, ~60 ms estimado en el Cortex-A72. A 1280x720 serían
    # ~167 ms, el 83 % de un núcleo a 5 análisis/s. La detección funciona
    # hasta con la credencial ocupando el 25 % del alto del cuadro.
    ancho: int = 640
    alto: int = 480
    analisis_por_s: float = 5.0
    # Se ignora el MISMO identificador durante este tiempo. Uno distinto
    # pasa de inmediato, para no bloquear a quien viene detrás.
    enfriamiento_s: float = 5.0


@dataclass
class RegistroCfg:
    """Credenciales registradas: quién tiene acceso y con qué rol."""
    ruta: str = "/var/lib/acceso/credenciales.json"
    directorio_credenciales: str = "/var/lib/acceso/credenciales"
```

### 1.2 Dos campos en `Config`

```python
    qr: QrCfg = field(default_factory=QrCfg)
    registro: RegistroCfg = field(default_factory=RegistroCfg)
```

### 1.3 Dos entradas en el diccionario `mapa` de `cargar()`

```python
        "qr": cfg.qr, "registro": cfg.registro,
```

### 1.4 Secciones nuevas en `acceso.conf`

```ini
[qr]
habilitado      = true
ancho           = 640
alto            = 480
analisis_por_s  = 5.0
enfriamiento_s  = 5.0

[registro]
ruta                    = /var/lib/acceso/credenciales.json
directorio_credenciales = /var/lib/acceso/credenciales
```

> Cuidado: ya existe una sección `[registro]` para el nivel de log. **No es
> la misma.** Si el nombre choca, renombrar la nueva a `[credenciales]` y
> ajustar la clave del diccionario `mapa`.

---

## 2. `pipeline.py`

### 2.1 Importar numpy arriba

```python
import numpy as np
```

### 2.2 El constructor recibe el lector

```python
    def __init__(self, cfg: Config, buffer: BufferCircular,
                 lector_qr=None) -> None:
        ...
        self._lector_qr = lector_qr
        self._appsink_qr: Gst.Element | None = None
```

### 2.3 Rama nueva en `descripcion()`

Pegar **justo antes** del `return " ".join(partes)`:

```python
        if c.qr.habilitado and self._lector_qr is not None:
            # Cuelga de t_raw (video SIN comprimir): OpenCV necesita imágenes,
            # no H.264. Formato BGR porque es el nativo de OpenCV; pedirlo
            # aquí evita una conversión en Python por cada cuadro.
            #
            # videorate baja a 5 fps ANTES de escalar y convertir: así esos
            # dos elementos trabajan sobre 5 cuadros por segundo y no sobre 30.
            #
            # leaky=downstream con un solo buffer: si el detector se atrasa,
            # interesa el presente. Un QR de hace dos segundos ya no sirve
            # para decidir, y acumular cola solo agregaría retraso.
            partes.append(
                f"t_raw. ! queue max-size-buffers=1 leaky=downstream "
                f"! videorate ! video/x-raw,framerate={int(c.qr.analisis_por_s)}/1 "
                f"! videoscale ! videoconvert "
                f"! video/x-raw,format=BGR,width={c.qr.ancho},height={c.qr.alto} "
                f"! appsink name=qr emit-signals=true sync=false "
                f"max-buffers=1 drop=true"
            )
```

### 2.4 Conectar el callback en `construir()`

Después de la línea que conecta `new-sample` del appsink de captura:

```python
        self._appsink_qr = self._pipeline.get_by_name("qr")
        if self._appsink_qr is not None and self._lector_qr is not None:
            self._appsink_qr.connect("new-sample", self._al_llegar_cuadro_qr)
```

### 2.5 Callback nuevo

Pegar junto a `_al_llegar_muestra`:

```python
    def _al_llegar_cuadro_qr(self, sink: Gst.Element) -> Gst.FlowReturn:
        """Entrega el cuadro al lector de QR. B5: copiar y retornar.

        La detección NO ocurre aquí. Este callback corre en el hilo de
        GStreamer: analizar la imagen dentro frenaría la tubería entera,
        incluidas la transmisión y la grabación. El lector tiene su propio
        hilo y toma el último cuadro cuando está libre.
        """
        muestra = sink.emit("pull-sample")
        if muestra is None:
            return Gst.FlowReturn.OK

        buf = muestra.get_buffer()
        caps = muestra.get_caps().get_structure(0)
        ancho = caps.get_value("width")
        alto = caps.get_value("height")

        ok, info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK
        try:
            # np.frombuffer NO copia: apunta a memoria de GStreamer, que se
            # libera en el unmap de abajo. El .copy() es obligatorio, no una
            # precaución: sin él el lector leería memoria ya liberada.
            cuadro = np.frombuffer(info.data, dtype=np.uint8)
            cuadro = cuadro.reshape((alto, ancho, 3)).copy()
            self._lector_qr.entregar_cuadro(cuadro)
        except ValueError as exc:
            log.warning("cuadro QR con forma inesperada: %s", exc)
        finally:
            buf.unmap(info)

        return Gst.FlowReturn.OK
```

---

## 3. `servicio.py`

### 3.1 Imports

```python
from .credencial import generar_credencial, verificar
from .lector_qr import LectorQR
from .registro import RegistroCredenciales, Rol
```

### 3.2 En `__init__`, después de `self._bitacora`

```python
        # CU-11/CU-12: credenciales registradas
        self._registro = RegistroCredenciales(cfg.registro.ruta)

        # CU-13: lector de QR. Se construye antes que el pipeline porque
        # este necesita saber si debe agregar la rama de cuadros crudos.
        self._lector: LectorQR | None = None
        if cfg.qr.habilitado:
            self._lector = LectorQR(
                self._al_detectar_qr,
                enfriamiento_s=cfg.qr.enfriamiento_s,
                periodo_s=1.0 / max(cfg.qr.analisis_por_s, 0.1),
            )
```

> El `PipelineAcceso(...)` que ya existe pasa a ser
> `PipelineAcceso(cfg, self._buffer, self._lector)`, y debe quedar **después**
> de esas líneas.

### 3.3 En `ejecutar()`, tras `self._pipeline.iniciar()`

```python
        if self._lector is not None:
            self._lector.iniciar()
```

### 3.4 En `_apagar()`, antes de `self._pipeline.detener()`

```python
        if self._lector is not None:
            self._lector.detener()
```

### 3.5 Comandos nuevos en `_procesar_comando`

Antes del `log.warning("comando no reconocido...")`:

```python
        if verbo == "ALTA":
            return self._alta(partes[1] if len(partes) > 1 else "")
        if verbo == "BAJA":
            return self._baja(partes[1] if len(partes) > 1 else "")
        if verbo == "LISTAR":
            return True, self._registro.resumen()
```

### 3.6 Métodos nuevos

```python
    # ------------------------------------------------------------------ #
    # CU-11 / CU-12: gestión de credenciales por el vigilante
    # ------------------------------------------------------------------ #
    def _alta(self, argumentos: str) -> tuple[bool, str]:
        """ALTA <rol> <nombre completo>

        El rol va primero porque es una sola palabra: así el nombre puede
        tener los espacios que haga falta sin necesitar comillas.
        """
        partes = argumentos.split(maxsplit=1)
        if len(partes) < 2:
            return False, "uso: ALTA <rol> <nombre>   roles: " + \
                   ", ".join(r.value for r in Rol)
        rol, nombre = partes[0], partes[1]

        try:
            cred = self._registro.alta(nombre, rol)
        except ValueError as exc:
            return False, str(exc)

        # La credencial se genera y se VERIFICA: una que no se puede leer es
        # peor que no tenerla, porque el fallo aparece recién cuando la
        # persona está en la puerta.
        ruta = os.path.join(self._cfg.registro.directorio_credenciales,
                            f"{cred.identificador}.png")
        try:
            generar_credencial(ruta, cred.identificador, cred.nombre, cred.rol)
            if not verificar(ruta, cred.identificador):
                return False, (f"{cred.identificador} registrado, pero la "
                               "credencial generada no se decodifica")
        except Exception as exc:                      # noqa: BLE001
            log.error("no se pudo generar la credencial: %s", exc)
            return True, (f"{cred.identificador} registrado, pero falló la "
                          f"generación del PNG: {exc}")

        self._difundir(f"ALTA {cred.identificador} {cred.rol} {cred.nombre}")
        return True, (f"{cred.identificador} | {cred.nombre} | {cred.rol} | "
                      f"credencial en {ruta}")

    def _baja(self, argumentos: str) -> tuple[bool, str]:
        """BAJA <identificador> [motivo]"""
        partes = argumentos.split(maxsplit=1)
        if not partes:
            return False, "uso: BAJA <identificador> [motivo]"
        ident = partes[0]
        motivo = partes[1] if len(partes) > 1 else None

        try:
            cred = self._registro.baja(ident, motivo)
        except ValueError as exc:
            return False, str(exc)

        self._difundir(f"BAJA {cred.identificador} {cred.nombre}")
        return True, f"acceso revocado: {cred.identificador} | {cred.nombre}"

    # ------------------------------------------------------------------ #
    # CU-13: llega una lectura de QR
    # ------------------------------------------------------------------ #
    def _al_detectar_qr(self, identificador: str, instante: float) -> None:
        """Lo llama el hilo del lector, nunca el de GStreamer (RNF-4).

        Tres caminos:
          * credencial activa con rol de acceso automático -> se resuelve sola
          * credencial activa de visitante                 -> escala al vigilante
          * identificador desconocido o dado de baja       -> escala al vigilante

        Los dos últimos usan el flujo de CU-3 que ya existe: si el vigilante
        no responde dentro del plazo, vence y se deniega (CU-5).
        """
        cred = self._registro.buscar(identificador)

        if cred is None:
            log.warning("QR no registrado o revocado: %s", identificador)
            ok, mensaje = self._nueva_solicitud(f"QR-{identificador}")
            if ok:
                self._difundir(f"QR-DESCONOCIDO {identificador} "
                               "requiere decision del vigilante")
            return

        rol = cred.rol_enum()
        etiqueta = f"{cred.identificador}-{cred.nombre.replace(' ', '_')}"

        if rol.acceso_automatico():
            log.info("QR AUTORIZADO: %s | %s | %s",
                     cred.identificador, cred.nombre, cred.rol)
            ok, _ = self._nueva_solicitud(etiqueta)
            if ok:
                self._difundir(f"QR-AUTORIZADO {cred.identificador} "
                               f"{cred.rol} {cred.nombre}")
                # La solicitud ya está abierta: resolverla de inmediato pasa
                # por el mismo camino que una decisión del vigilante, así el
                # clip, la bitácora y el buzzer funcionan igual.
                self._resolver(True)
            return

        log.info("QR de visitante: %s | %s (requiere confirmación)",
                 cred.identificador, cred.nombre)
        ok, _ = self._nueva_solicitud(etiqueta)
        if ok:
            self._difundir(f"QR-VISITANTE {cred.identificador} {cred.nombre} "
                           "requiere decision del vigilante")
```

---

## Qué revisar al integrar

**`os` ya está importado** en `servicio.py`. No hace falta agregarlo.

**El orden en `__init__`** importa: el lector se construye antes que el
pipeline, porque este consulta `self._lector_qr` para decidir si agrega la
rama de cuadros crudos.

**El conflicto de `[registro]`** en el `acceso.conf`: ya existe una sección
con ese nombre para el nivel de log. Verificar y renombrar si hace falta.

**`numpy`** tiene que estar en la imagen. Viene con `python3-opencv`, pero
conviene confirmarlo en el destino con `python3 -c "import numpy"`.
