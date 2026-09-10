# Bitácora individual de trabajo

**Estudiante:** Daniel Chavarría García
**Rol en el equipo:** B — Plataforma (Yocto, BSP, imagen)
**Proyecto 1 — Sistema de control de acceso con Yocto Project y GStreamer**
**Taller de Sistemas Embebidos · TEC · II Semestre 2026**
**Prof. Dr. Ing. Johan Carvajal Godínez**

---

## Entorno de trabajo

| Elemento | Valor |
|---|---|
| Host | WSL2 · Ubuntu 24.04 sobre Windows (DESKTOP-R72NF1I) |
| RAM / swap | 7.6 GiB / 8 GiB |
| Yocto | Poky / oe-core `yocto-6.0.2` (serie Wrynose) |
| Máquina destino | `raspberrypi4-64` |
| Directorio de compilación | `~/proyecto-acceso/build` |
| Capas | `~/proyecto-acceso/layers/` (enlaces a `~/taller-yocto/layers/`) |

---

## Registro de decisiones de diseño

| # | Fecha | Decisión | Alternativas consideradas | Justificación |
|---|---|---|---|---|
| D-01 | 2026-09-10 | Usar `DISTRO = "poky"` | Build distro-less (solo oe-core) | meta-raspberrypi declara Poky como su foco principal de pruebas; además da una base conocida de `DISTRO_FEATURES` sobre la cual activar `gobject-introspection-data` más adelante |
| D-02 | 2026-09-10 | `INIT_MANAGER = "systemd"` | sysvinit | RF-11 (arranque automático) y RF-12 (reinicio ante falla) se resuelven con una unidad de servicio; el cierre ordenado del MP4 requiere `TimeoutStopSec` |
| D-03 | 2026-09-10 | Capas compartidas por enlace simbólico con `~/taller-yocto` | Clonar un árbol nuevo | Evita duplicar ~2 GiB de fuentes y permite reutilizar 42 GiB de caché; los dos builds quedan independientes |
| D-04 | 2026-09-10 | Aceptar `synaptics-killswitch` en `LICENSE_FLAGS_ACCEPTED` | Excluir `packagegroup-base-extended` | `core-image-base` arrastra el firmware WiFi por diseño; el WiFi queda como respaldo si falla el cable en la demostración |
| D-05 |  |  |  |  |

---

## Registro de tiempos de compilación

| Fecha | Objetivo | Inicio | Fin | Duración | Notas |
|---|---|---|---|---|---|
| 2026-09-10 | `core-image-base` | 11:09 |  |  | Primera compilación para RPi4 |
|  |  |  |  |  |  |

---

## Registro de problemas y soluciones

| # | Fecha | Síntoma | Causa raíz | Solución | Tiempo perdido |
|---|---|---|---|---|---|
| P-01 | 2026-09-10 | `bitbake -e` sin salida y código 127 | Terminal nueva sin `oe-init-build-env`; el 127 de bash significa "comando no encontrado", no un fallo de Yocto | Re-ejecutar `source layers/openembeddedcore/oe-init-build-env build` | ~10 min |
| P-02 | 2026-09-10 | Fallo de parseo de `local.conf` | Comilla de apertura faltante en `SSTATE_DIR` y typo `sysyemd`; una comilla sin cerrar hace que BitBake lea el resto del archivo como cadena | Corrección con `sed`; verificación con `bitbake -e` antes de compilar | ~15 min |
| P-03 | 2026-09-10 | `Nothing RPROVIDES 'linux-firmware-rpidistro-bcm43456'` | Licencia restringida bloqueada por defecto (mecanismo de cumplimiento de Yocto) | `LICENSE_FLAGS_ACCEPTED += "synaptics-killswitch"` | ~5 min |
| P-04 | 2026-09-10 | Aviso: sstate compartido pero base de hashes local → sin reutilización | `BB_HASHSERVE_DB_DIR` apuntaba dentro del build | `BB_HASHSERVE_DB_DIR = "${SSTATE_DIR}"` | Detectado con `--dry-run` antes de compilar |
| P-05 |  |  |  |  |  |

---

## Entradas diarias

### 2026-09-10 · ___ h

**Objetivo de la sesión**

Preparar el árbol de capas y la configuración de compilación para la máquina
`raspberrypi4-64`, y lanzar la primera imagen base.

**Actividades**

1. Inventario del entorno: espacio, memoria, capas y caché disponibles.
2. Verificación de compatibilidad de serie entre capas (`LAYERSERIES_COMPAT`).
3. Creación de la capa `meta-acceso` con `bitbake-layers create-layer`.
4. Registro de ocho capas en `bblayers.conf`.
5. Configuración de `local.conf` y verificación con `bitbake -e`.
6. Validación previa con `bitbake core-image-base --dry-run`.

**Comandos relevantes**

```bash
source layers/openembeddedcore/oe-init-build-env build
bitbake-layers create-layer ../layers/meta-acceso
bitbake-layers add-layer ../layers/meta-raspberrypi
bitbake-layers show-layers
bitbake -e | grep -E "^(DISTRO|MACHINE|INIT_MANAGER)="
bitbake core-image-base --dry-run
```

**Resultados**

- Ocho capas registradas, todas compatibles con la serie `wrynose`.
- `local.conf` parsea sin errores; las seis variables clave verificadas.
- (pendiente: resultado de la compilación)

**Aprendizajes**

- `--dry-run` calcula el grafo completo de tareas sin ejecutarlas: detecta
  dependencias irresolubles y problemas de licencia antes de invertir horas.
- Las prioridades de capa determinan quién gana cuando dos definen la misma
  receta; el BSP usa 9 para poder sobrescribir recetas de oe-core.
- Un sstate compartido no se reutiliza si la base de equivalencia de hashes
  vive dentro del build.

**Pendientes**

- [ ] Completar la compilación de `core-image-base`
- [ ] Grabar la microSD y verificar arranque con consola
- [ ] Confirmar modelo exacto de la cámara (V2/IMX219 o V3/IMX708)
- [ ] Confirmar disponibilidad física de RPi4, microSD y módulo de relé

**Coordinación con el compañero**

_Pendiente: acordar versión 1.0 del contrato de integración._

---

### AAAA-MM-DD · ___ h

**Objetivo de la sesión**

**Actividades**

1.

**Comandos relevantes**

```bash

```

**Resultados**

**Problemas encontrados**

| Síntoma | Hipótesis | Qué se probó | Resultado |
|---|---|---|---|
|  |  |  |  |

**Aprendizajes**

**Pendientes**

- [ ]

**Coordinación con el compañero**

---

## Resumen final

_(se completa al cierre del proyecto)_

- Horas totales dedicadas:
- Requerimientos verificados personalmente:
- Contribución principal al equipo:
- Qué haría distinto en un proyecto siguiente:
