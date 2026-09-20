# Sistema de control de acceso — aplicación (Rol A)

Proyecto 1 · Taller de Sistemas Embebidos · TEC

## Arquitectura

```
fuente ─ caps ─ queue ─ tee_raw ─ queue ─ [conv] ─ encoder ─ h264parse ─ tee_h264 ─┬─ queue ─ splitmuxsink   (evidencia continua)
                                                                                   ├─ queue ─ rtph264pay ─ udpsink  (vigilancia)
                                                                                   └─ queue ─ appsink → buffer circular
```

Cuatro hilos (H1):

| Hilo | Función |
|---|---|
| GStreamer | captura, codifica, transmite, graba. Nunca espera |
| Eventos | lee decisiones del vigilante desde el FIFO |
| Por solicitud | espera la decisión con su plazo (H2) y escribe el clip |
| Reconexión | E3: reintenta tras falla de la cámara |

## Módulos

| Archivo | Responsabilidad | Ítems |
|---|---|---|
| `config.py` | configuración INI sin dependencias externas | RF-13 |
| `buffer_circular.py` | pre-evento en cuadros H.264 comprimidos | B4, B5 |
| `pipeline.py` | tubería GStreamer, appsink, watch de bus | A*, B*, E1, E4 |
| `decision.py` | plazo de decisión y bitácora persistente | H2, H6, RF-4 |
| `actuador.py` | LED de estado por GPIO con pulso | RF-5, CU-4 |
| `servicio.py` | orquestación e hilos | H1, E3 |

## Uso

```bash
# ver la tubería sin ejecutarla
python3 -m acceso -c config/acceso.conf --mostrar-tuberia

# arrancar el servicio
python3 -m acceso -c config/acceso.conf --dot grafos

# desde otra terminal: disparar los casos de uso
echo "SOLICITUD ID-001" > /tmp/acceso-eventos
echo "PERMITIR"         > /tmp/acceso-eventos

# consultar la bitácora (H6)
python3 -m acceso -c config/acceso.conf --ver-bitacora

# receptor, en la SEGUNDA computadora
./scripts/receptor-vigilancia.sh 5000
```

## Decisiones de diseño registradas

- **Cuadros comprimidos en el búfer**: 10 s ocupan ~2.2 MiB en vez de 415 MB de cuadros crudos. Exige recortar en cuadro clave, resuelto retrocediendo al IDR anterior.
- **H2, vencimiento definitivo**: al vencer el plazo la solicitud se cierra. Un `PERMITIR` tardío es rechazado; de lo contrario la puerta se abriría después de que el sistema ya denegó.
- **E3, reconexión con alerta**: el proceso no muere; registra la alerta y reintenta cada 5 s indefinidamente.
- **H6, archivo JSONL con `fsync`**: sobrevive a corte de energía, no solo a cierre ordenado. Se inspecciona con `cat`.
