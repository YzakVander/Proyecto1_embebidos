"""Canal de red entre el puesto de vigilancia y la Raspberry Pi (CU-3, RF-3).

El vigilante esta en OTRA computadora, asi que el FIFO local no le sirve.
Este modulo abre un servidor TCP que acepta los mismos comandos que el FIFO:

    SOLICITUD [id]   abre una solicitud de acceso y arranca el plazo de
                     decision. Sin id, la placa genera uno con la fecha y
                     hora de apertura (S-20260930-143012)
    PERMITIR         resuelve la solicitud pendiente como permitida
    DENEGAR          resuelve la solicitud pendiente como denegada
    ESTADO           informa si hay solicitud pendiente y cuanto plazo queda
    PING             no toca el estado; sirve para medir el tiempo de ida y vuelta

Protocolo: texto, una linea por mensaje, terminada en '\\n'.
  * Cada comando recibe exactamente UNA respuesta: 'OK ...' o 'ERROR ...'.
  * Ademas el servidor difunde a todos los clientes conectados lineas
    'EVENTO ...' que el vigilante no pidio:
        EVENTO SOLICITUD <id> plazo=<s>s    se abrio una solicitud
        EVENTO RESULTADO <id> <resultado>   permitido | denegado |
                                            denegado_por_vencimiento
    El temporizador corre en la placa: asi el vigilante se entera de un
    vencimiento aunque no haya enviado nada.

Por que TCP y no UDP
--------------------
Una decision de acceso no se puede perder en la red: TCP garantiza entrega y
orden, y la respuesta 'OK' le confirma al vigilante que la placa la recibio.

RF-3 (deteccion en <= 100 ms)
-----------------------------
El 'OK' se envia DESPUES de procesar el comando. El cliente mide el tiempo
entre enviar y recibir el 'OK' (RTT). Como ese RTT incluye la ida, el
procesamiento y la vuelta, si RTT <= 100 ms la deteccion tambien lo es, sin
necesidad de sincronizar los relojes de las dos maquinas.
TCP_NODELAY es obligatorio: sin el, el algoritmo de Nagle junto con el ACK
retardado puede agregar ~40 ms a mensajes tan cortos como estos.
"""

from __future__ import annotations

import logging
import socket
import socketserver
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)

# Funcion que procesa un comando y devuelve (exito, mensaje de respuesta)
Procesador = Callable[[str], "tuple[bool, str]"]

LARGO_MAX_LINEA = 256   # evita que un cliente mal portado llene la memoria


class _ServidorTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True    # permite reiniciar el servicio sin esperar TIME_WAIT
    daemon_threads = True         # los hilos de cliente no impiden cerrar el proceso


class ServidorDecisiones:
    """Servidor TCP de comandos del vigilante. Un hilo por cliente conectado."""

    def __init__(self, puerto: int, procesar: Procesador,
                 clientes_permitidos: str = "") -> None:
        self._puerto = puerto
        self._procesar = procesar
        # Lista blanca de IPs. Cualquiera en la red podria abrir la puerta,
        # asi que en la demo conviene restringirla a la IP del vigilante.
        self._permitidos = {ip.strip() for ip in clientes_permitidos.split(",") if ip.strip()}
        self._clientes: set = set()          # wfile de cada cliente conectado
        self._lock = threading.Lock()        # protege _clientes y las escrituras
        self._srv: _ServidorTCP | None = None

    # ------------------------------------------------------------------ #
    def iniciar(self) -> None:
        servidor = self   # el manejador necesita acceso a esta instancia

        class Manejador(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                servidor._atender_cliente(self)

        self._srv = _ServidorTCP(("0.0.0.0", self._puerto), Manejador)
        threading.Thread(target=self._srv.serve_forever, name="red-decisiones",
                         daemon=True).start()
        log.info("canal de decisiones escuchando en TCP %d%s", self._puerto,
                 f" (solo {sorted(self._permitidos)})" if self._permitidos else "")

    def detener(self) -> None:
        if self._srv is not None:
            self._srv.shutdown()
            self._srv.server_close()
            self._srv = None

    def difundir(self, texto: str) -> None:
        """Envia una linea 'EVENTO ...' a todos los clientes conectados."""
        with self._lock:
            clientes = list(self._clientes)
        for wfile in clientes:
            self._enviar(wfile, "EVENTO " + texto)

    # ------------------------------------------------------------------ #
    def _atender_cliente(self, h: socketserver.StreamRequestHandler) -> None:
        ip = h.client_address[0]
        if self._permitidos and ip not in self._permitidos:
            log.warning("conexion rechazada desde %s (no esta en red_clientes)", ip)
            self._enviar(h.wfile, "ERROR cliente no autorizado")
            return

        h.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        with self._lock:
            self._clientes.add(h.wfile)
        log.info("puesto de vigilancia conectado: %s", ip)
        self._enviar(h.wfile, "OK conectado al sistema de control de acceso")

        try:
            while True:
                linea = h.rfile.readline(LARGO_MAX_LINEA)
                if not linea:            # el cliente cerro la conexion
                    break
                t0 = time.monotonic()
                texto = linea.decode("utf-8", errors="replace").strip()
                if not texto:
                    continue
                ok, mensaje = self._procesar(texto)
                self._enviar(h.wfile, ("OK " if ok else "ERROR ") + mensaje)
                log.info("red %s: '%s' procesado en %.2f ms", ip, texto,
                         (time.monotonic() - t0) * 1000.0)
        except OSError as exc:
            log.warning("conexion con %s interrumpida: %s", ip, exc)
        finally:
            with self._lock:
                self._clientes.discard(h.wfile)
            log.info("puesto de vigilancia desconectado: %s", ip)

    def _enviar(self, wfile, texto: str) -> None:
        # Un solo lock para todas las escrituras: la respuesta de un comando y
        # una difusion simultanea no pueden mezclar sus bytes en el socket.
        try:
            with self._lock:
                wfile.write((texto + "\n").encode("utf-8"))
        except OSError:
            with self._lock:
                self._clientes.discard(wfile)
