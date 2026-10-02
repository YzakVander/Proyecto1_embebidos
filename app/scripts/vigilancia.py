#!/usr/bin/env python3
"""Puesto de vigilancia: una sola terminal para todo (CU-1, CU-2, CU-3).

Reemplaza a `nc` y a las terminales aparte del receptor y de la recoleccion:

  * Abre la ventana del video en vivo (misma tuberia que
    receptor-vigilancia.sh) en segundo plano.
  * Se conecta al canal de decisiones de la placa (TCP 5001) y funciona
    igual que nc: lo que se escribe va a la placa y se muestran sus
    respuestas (OK / ERROR) y sus avisos (EVENTO).
  * Atiende comandos LOCALES que no se envian a la placa:
        RECOLECTAR  trae evidencia, eventos, bitacora y QR activos
                    (corre recolectar-evidencia.sh en segundo plano)
        BORRAR_VIDEOS_LOG
                    borra en la placa los videos de evidencia, los clips
                    de eventos y la bitacora (pide confirmacion)
        VIDEO       vuelve a abrir la ventana del video
        AYUDA       lista de comandos
        SALIR       cierra el cliente (la placa sigue funcionando)
  * Muestra el tiempo de ida y vuelta de cada comando: con PING es la
    medicion de RF-3 (<= 100 ms).

Al conectarse, la placa redirige el video a la IP de esta computadora
(streaming.seguir_cliente), asi que no hace falta configurar nada.

Solo usa la biblioteca estandar de Python.

Uso:  ./vigilancia.py                       (placa en 172.21.255.220)
      ./vigilancia.py --ip 172.21.255.50
      ./vigilancia.py --sin-video
"""

from __future__ import annotations

import argparse
import collections
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import readline   # historial con las flechas y para redibujar la linea
except ImportError:   # pragma: no cover (Windows)
    readline = None

AQUI = Path(__file__).resolve().parent
SCRIPT_RECOLECTAR = AQUI / "recolectar-evidencia.sh"

REMOTO = "/var/lib/acceso"              # StateDirectory del servicio en la placa
SERVICIO = "acceso-control"
# Mismas opciones que recolectar-evidencia.sh: sin verificar la huella, que
# cambia al regrabar la microSD (aceptable en una red de laboratorio).
SSH_OPC = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
           "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=5",
           "-o", f"Port={os.environ.get('PUERTO', '22')}"]

COMANDOS_PLACA = {
    "SOLICITUD [id]": "abre una solicitud a mano (persona sin credencial)",
    "PERMITIR": "resuelve la solicitud pendiente como permitida",
    "DENEGAR": "resuelve la solicitud pendiente como denegada",
    "ESTADO": "solicitud pendiente y plazo restante",
    "ALTA <rol> <nombre>": "registra una credencial (vigilante, mantenimiento, visitante)",
    "BAJA <id> [motivo]": "revoca una credencial",
    "LISTAR": "credenciales activas",
    "REGENERAR_QR": "rehace las imagenes de las credenciales activas (mismos QR)",
    "BORRAR_CREDENCIALES": "elimina TODAS las credenciales y sus imagenes (pide confirmacion)",
    "PING": "mide el tiempo de ida y vuelta (RF-3)",
}
COMANDOS_LOCALES = {
    "RECOLECTAR": "trae evidencia, eventos, bitacora y QR activos a esta computadora",
    "BORRAR_VIDEOS_LOG": "borra en la placa evidencia, eventos y bitacora (pide confirmacion)",
    "VIDEO": "vuelve a abrir la ventana del video",
    "AYUDA": "esta lista",
    "SALIR": "cierra el cliente (la placa sigue funcionando)",
}


# ---------------------------------------------------------------------- #
# Consola: escribir lineas sin romper lo que el usuario esta tecleando
# ---------------------------------------------------------------------- #
class Consola:
    PROMPT = "vigilancia> "

    def __init__(self) -> None:
        self._lock = threading.Lock()
        color = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
        self._c = {
            "ok": "\033[32m" if color else "",
            "error": "\033[31m" if color else "",
            "evento": "\033[33m" if color else "",
            "info": "\033[36m" if color else "",
            "fin": "\033[0m" if color else "",
        }

    def escribir(self, texto: str, tipo: str = "") -> None:
        """Imprime una linea y vuelve a dibujar el prompt con lo ya tecleado."""
        ini, fin = self._c.get(tipo, ""), self._c["fin"] if tipo else ""
        with self._lock:
            tecleado = readline.get_line_buffer() if readline else ""
            sys.stdout.write(f"\r\033[K{ini}{texto}{fin}\n{self.PROMPT}{tecleado}")
            sys.stdout.flush()


# ---------------------------------------------------------------------- #
# Ventana de video (CU-1)
# ---------------------------------------------------------------------- #
class Video:
    def __init__(self, puerto: int, consola: Consola) -> None:
        self._puerto = puerto
        self._consola = consola
        self._proc: subprocess.Popen | None = None

    def abrir(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._consola.escribir("el video ya esta abierto", "info")
            return
        if shutil.which("gst-launch-1.0") is None:
            self._consola.escribir("no se encontro gst-launch-1.0: el video no se abre "
                                   "(sudo apt install gstreamer1.0-tools)", "error")
            return
        # Misma tuberia que receptor-vigilancia.sh, sin -v para no llenar la consola
        tuberia = (
            f"udpsrc port={self._puerto} "
            "caps=application/x-rtp,media=(string)video,clock-rate=(int)90000,"
            "encoding-name=(string)H264,payload=(int)96 "
            "! rtpjitterbuffer latency=100 "
            "! rtph264depay ! h264parse ! avdec_h264 "
            "! videoconvert ! autovideosink sync=false"
        )
        self._proc = subprocess.Popen(
            ["gst-launch-1.0", "-q", *tuberia.split()],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        threading.Thread(target=self._vigilar, args=(self._proc,),
                         name="video", daemon=True).start()
        self._consola.escribir(f"video: escuchando en UDP {self._puerto}", "info")

    def _vigilar(self, proc: subprocess.Popen) -> None:
        proc.wait()
        if proc is self._proc:
            self._consola.escribir("la ventana del video se cerro "
                                   "(escribir VIDEO para abrirla de nuevo)", "info")

    def cerrar(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None


# ---------------------------------------------------------------------- #
# Canal de decisiones (CU-3)
# ---------------------------------------------------------------------- #
class Canal:
    """Conexion TCP con la placa, con reconexion automatica.

    La placa responde exactamente UNA linea OK/ERROR por comando y en orden,
    asi que basta una cola con la hora de envio de cada comando para medir
    su tiempo de ida y vuelta. Las lineas EVENTO no son respuestas.
    """

    REINTENTO_S = 3.0

    def __init__(self, ip: str, puerto: int, consola: Consola) -> None:
        self._dir = (ip, puerto)
        self._consola = consola
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._enviados: collections.deque = collections.deque()  # (comando, t0)
        self._activo = True

    def iniciar(self) -> None:
        threading.Thread(target=self._bucle, name="canal", daemon=True).start()

    def conectado(self) -> bool:
        return self._sock is not None

    def enviar(self, comando: str) -> bool:
        with self._lock:
            if self._sock is None:
                return False
            try:
                self._enviados.append((comando, time.monotonic()))
                self._sock.sendall((comando + "\n").encode("utf-8"))
                return True
            except OSError:
                self._enviados.pop()
                return False

    def cerrar(self) -> None:
        self._activo = False
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self._sock.close()
                self._sock = None

    # ------------------------------------------------------------------ #
    def _bucle(self) -> None:
        avisado = False
        while self._activo:
            try:
                sock = socket.create_connection(self._dir, timeout=5)
            except OSError as exc:
                if not avisado:
                    self._consola.escribir(
                        f"sin conexion con {self._dir[0]}:{self._dir[1]} ({exc}); "
                        f"reintentando cada {self.REINTENTO_S:.0f} s ...", "error")
                    avisado = True
                time.sleep(self.REINTENTO_S)
                continue

            avisado = False
            sock.settimeout(None)
            # Sin Nagle: los comandos son lineas cortas y el RTT se mediria mal
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self._lock:
                self._sock = sock
                self._enviados.clear()
            self._leer(sock)
            with self._lock:
                self._sock = None
                self._enviados.clear()
            if self._activo:
                self._consola.escribir("se perdio la conexion con la placa; "
                                       "reintentando ...", "error")
                time.sleep(self.REINTENTO_S)

    def _leer(self, sock: socket.socket) -> None:
        archivo = sock.makefile("r", encoding="utf-8", errors="replace")
        try:
            for linea in archivo:
                self._mostrar(linea.rstrip("\n"), time.monotonic())
        except OSError:
            pass
        finally:
            archivo.close()

    def _mostrar(self, linea: str, t_llegada: float) -> None:
        if linea.startswith("EVENTO "):
            self._consola.escribir(linea, "evento")
            return
        if linea.startswith(("OK", "ERROR")):
            tipo = "ok" if linea.startswith("OK") else "error"
            with self._lock:
                enviado = self._enviados.popleft() if self._enviados else None
            if enviado is None:
                # Saludo al conectarse (o rechazo por red_clientes)
                self._consola.escribir(linea, tipo)
            else:
                rtt_ms = (t_llegada - enviado[1]) * 1000.0
                self._consola.escribir(f"{linea}   [{rtt_ms:.1f} ms]", tipo)
            return
        # Continuacion de una respuesta de varias lineas (p. ej. LISTAR)
        self._consola.escribir(linea)


# ---------------------------------------------------------------------- #
# Recoleccion (CU-2)
# ---------------------------------------------------------------------- #
class Recolector:
    def __init__(self, ip: str, clave: str | None, consola: Consola) -> None:
        self._ip = ip
        self._clave = clave
        self._consola = consola
        self._hilo: threading.Thread | None = None

    def en_curso(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def lanzar(self) -> None:
        if self.en_curso():
            self._consola.escribir("ya hay una recoleccion en curso", "info")
            return
        if not SCRIPT_RECOLECTAR.exists():
            self._consola.escribir(f"no se encontro {SCRIPT_RECOLECTAR}", "error")
            return
        # En segundo plano: mientras se copia, el vigilante tiene que poder
        # seguir resolviendo solicitudes.
        self._hilo = threading.Thread(target=self._correr, name="recolectar", daemon=True)
        self._hilo.start()

    def _correr(self) -> None:
        entorno = dict(os.environ, IP=self._ip)
        if self._clave is not None:
            entorno["CLAVE"] = self._clave
        self._consola.escribir("recoleccion iniciada (se puede seguir operando)", "info")
        try:
            proc = subprocess.Popen(
                ["bash", str(SCRIPT_RECOLECTAR)], env=entorno,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, errors="replace")
        except OSError as exc:
            self._consola.escribir(f"no se pudo correr la recoleccion: {exc}", "error")
            return
        assert proc.stdout is not None
        for linea in proc.stdout:
            linea = linea.rstrip("\n")
            if linea:
                self._consola.escribir(f"[recolectar] {linea}", "info")
        codigo = proc.wait()
        if codigo == 0:
            self._consola.escribir("recoleccion terminada", "ok")
        else:
            self._consola.escribir(f"la recoleccion fallo (codigo {codigo})", "error")


# ---------------------------------------------------------------------- #
# Borrado de evidencia y bitacora en la placa
# ---------------------------------------------------------------------- #
class Borrador:
    """Borra en la placa los videos de evidencia, los clips y la bitacora.

    Se hace por SSH y no por el canal 5001: asi no hace falta cambiar el
    codigo de la placa, y nadie conectado al canal de decisiones puede borrar
    la evidencia (por la misma razon el servidor rechaza SALIR por red).

    El servicio se detiene antes de borrar: el segmento en curso se cierra
    bien y la app no escribe la bitacora mientras se vacia. Se vuelve a
    arrancar aunque el borrado falle, para no dejar la placa sin servicio.
    Las credenciales no se tocan.
    """

    # 10 = no se pudo detener el servicio (no se borro nada)
    # 11 = se borro, pero el servicio no volvio a arrancar
    COMANDO = (
        f"systemctl stop {SERVICIO} || exit 10; "
        f"rm -f {REMOTO}/evidencia/* {REMOTO}/eventos/* "
        f"&& : > {REMOTO}/accesos.log; err=$?; "
        f"systemctl start {SERVICIO} || exit 11; "
        f"du -sh {REMOTO}/evidencia {REMOTO}/eventos; "
        f"echo \"$(wc -l < {REMOTO}/accesos.log) entradas en accesos.log\"; "
        "exit $err"
    )

    def __init__(self, ip: str, clave: str | None, consola: Consola) -> None:
        self._ip = ip
        # Misma contrasena que la recoleccion: vacia por defecto, como la imagen
        self._clave = clave if clave is not None else os.environ.get("CLAVE", "")
        self._consola = consola
        self._hilo: threading.Thread | None = None

    def en_curso(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def lanzar(self) -> None:
        self._hilo = threading.Thread(target=self._correr, name="borrar", daemon=True)
        self._hilo.start()

    def _correr(self) -> None:
        self._consola.escribir("borrando en la placa (el servicio se reinicia: "
                               "la conexion se corta unos segundos) ...", "info")
        try:
            proc = subprocess.run(
                ["sshpass", "-p", self._clave, "ssh", *SSH_OPC,
                 f"root@{self._ip}", self.COMANDO],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                errors="replace", timeout=90)
        except subprocess.TimeoutExpired:
            self._consola.escribir("el borrado no respondio en 90 s", "error")
            return
        for linea in (proc.stdout + proc.stderr).splitlines():
            if linea.strip():
                self._consola.escribir(f"[borrar] {linea}", "info")
        if proc.returncode == 0:
            self._consola.escribir("evidencia, eventos y bitacora borrados en la placa", "ok")
        elif proc.returncode == 10:
            self._consola.escribir("no se pudo detener el servicio: no se borro nada", "error")
        elif proc.returncode == 11:
            self._consola.escribir("se borro, pero el servicio NO volvio a arrancar: "
                                   "revisar la placa (systemctl status acceso-control)", "error")
        elif proc.returncode == 255:
            self._consola.escribir(f"no se pudo entrar por SSH a root@{self._ip} "
                                   "(IP o contrasena)", "error")
        else:
            self._consola.escribir(f"el borrado fallo (codigo {proc.returncode})", "error")


# ---------------------------------------------------------------------- #
def ayuda(consola: Consola) -> None:
    consola.escribir("Comandos para la placa:")
    for cmd, desc in COMANDOS_PLACA.items():
        consola.escribir(f"  {cmd:<22} {desc}")
    consola.escribir("Comandos locales (no se envian a la placa):")
    for cmd, desc in COMANDOS_LOCALES.items():
        consola.escribir(f"  {cmd:<22} {desc}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Puesto de vigilancia del control de acceso")
    ap.add_argument("--ip", default=os.environ.get("IP", "172.21.255.220"),
                    help="IP de la placa (por defecto 172.21.255.220)")
    ap.add_argument("--puerto", type=int, default=5001, help="canal de decisiones (5001)")
    ap.add_argument("--video-puerto", type=int, default=5000, help="UDP del video (5000)")
    ap.add_argument("--sin-video", action="store_true", help="no abrir la ventana del video")
    ap.add_argument("--clave", default=None,
                    help="contrasena de root para RECOLECTAR (por defecto vacia, "
                         "como la deja la imagen)")
    args = ap.parse_args()

    consola = Consola()
    video = Video(args.video_puerto, consola)
    canal = Canal(args.ip, args.puerto, consola)
    recolector = Recolector(args.ip, args.clave, consola)
    borrador = Borrador(args.ip, args.clave, consola)

    print(f"Puesto de vigilancia -> placa {args.ip}:{args.puerto}   (AYUDA para ver comandos)")
    # El video primero: cuando la placa redirija el stream al conectarnos,
    # el puerto UDP ya tiene que estar escuchando.
    if not args.sin_video:
        video.abrir()
    canal.iniciar()

    try:
        while True:
            try:
                texto = input(Consola.PROMPT).strip()
            except EOFError:          # Ctrl+D
                break
            if not texto:
                continue
            verbo = texto.split()[0].upper()
            if verbo == "SALIR":
                if recolector.en_curso() or borrador.en_curso():
                    consola.escribir("hay una recoleccion o un borrado en curso: "
                                     "esperar a que termine antes de SALIR", "error")
                    continue
                break
            if verbo == "AYUDA":
                ayuda(consola)
            elif verbo == "RECOLECTAR":
                if borrador.en_curso():
                    consola.escribir("hay un borrado en curso: esperar a que termine", "error")
                else:
                    recolector.lanzar()
            elif verbo == "BORRAR_VIDEOS_LOG":
                if recolector.en_curso():
                    # Borraria los archivos que la recoleccion esta copiando
                    consola.escribir("hay una recoleccion en curso: esperar a que "
                                     "termine antes de borrar", "error")
                elif borrador.en_curso():
                    consola.escribir("ya hay un borrado en curso", "info")
                elif shutil.which("sshpass") is None:
                    consola.escribir("falta sshpass (sudo apt install sshpass)", "error")
                else:
                    consola.escribir("Se borraran TODOS los videos de evidencia, los clips "
                                     "de eventos y la bitacora de la placa. Las credenciales "
                                     "se conservan.", "error")
                    try:
                        respuesta = input("Escribir SI para confirmar: ").strip()
                    except EOFError:
                        respuesta = ""
                    if respuesta == "SI":
                        borrador.lanzar()
                    else:
                        consola.escribir("borrado cancelado", "info")
            elif verbo == "BORRAR_CREDENCIALES":
                # Se confirma aqui y se envia con el SI que exige la placa
                consola.escribir("Se eliminaran TODAS las credenciales de la placa (activas "
                                 "y revocadas) y sus imagenes. Nadie podra entrar por QR "
                                 "hasta registrar credenciales nuevas.", "error")
                try:
                    respuesta = input("Escribir SI para confirmar: ").strip()
                except EOFError:
                    respuesta = ""
                if respuesta != "SI":
                    consola.escribir("borrado de credenciales cancelado", "info")
                elif not canal.enviar("BORRAR_CREDENCIALES SI"):
                    consola.escribir("sin conexion con la placa: el comando no se envio", "error")
            elif verbo == "VIDEO":
                video.abrir()
            elif not canal.enviar(texto):
                consola.escribir("sin conexion con la placa: el comando no se envio", "error")
    except KeyboardInterrupt:         # Ctrl+C
        pass
    finally:
        print()
        canal.cerrar()
        video.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
