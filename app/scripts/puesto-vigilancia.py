#!/usr/bin/env python3
"""Puesto de vigilancia con interfaz grafica (CU-1, CU-2, CU-3, CU-11, CU-12).

Una sola ventana para todo el trabajo del vigilante:

  Operacion     SOLICITUD / PERMITIR / DENEGAR / ESTADO, en botones.
  Credenciales  alta, baja, listado. La credencial recien generada se trae
                a esta computadora y se ABRE sola, lista para compartir.
  Galeria       miniaturas de los QR activos; doble clic para verlos grandes.
  Eventos       clips de 10 s de cada evento; doble clic para reproducirlos.
  Mediciones    RF-1 (fps recibidos) y RF-3 (RTT <= 100 ms), con veredicto.

La placa no necesita ningun cambio: ya devuelve la ruta de la credencial en
la respuesta de ALTA, y el resto se trae por scp.

    python3 puesto-vigilancia.py --ip 172.21.255.55
    python3 puesto-vigilancia.py --ip 127.0.0.1      (prueba local)

Requisitos:  python3-tk, python3-opencv, gstreamer1.0-tools y plugins
             good/bad/libav.  sshpass solo si la placa pide contrasena.
"""

from __future__ import annotations

import argparse
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk
except ImportError:
    sys.exit("Falta python3-tk.   sudo apt install python3-tk")

try:
    import cv2
except ImportError:
    cv2 = None

PUERTO_RTP = 5000
PUERTO_TCP = 5001
REMOTO = "/var/lib/acceso"
SERVICIO = "acceso-control"
SCRIPT_RECOLECTAR = Path(__file__).resolve().parent / "recolectar-evidencia.sh"
SSH_OPC = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
           "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=5"]

# Roles que reciben credencial con QR. El vigilante NO lleva: es quien decide
# los accesos y opera este puesto, no quien se identifica en la puerta.
ROLES_CON_QR = ("mantenimiento", "visitante")

RE_FPS = re.compile(r"current:\s*([0-9.]+).*?average:\s*([0-9.]+)")
RE_RUTA_CRED = re.compile(r"credencial en (\S+\.(?:bmp|png|jpe?g))", re.I)
EXT_IMAGEN = (".bmp", ".png", ".jpg", ".jpeg")

COLOR_OK = "#2f6b3f"
COLOR_ERR = "#8a3324"
COLOR_TENUE = "#6b6b6b"


def es_local(ip: str) -> bool:
    return ip in ("127.0.0.1", "localhost", "::1")


def abrir_con_el_sistema(ruta: Path) -> str:
    """Abre un archivo con el visor o reproductor del escritorio."""
    if sys.platform == "darwin":
        cmd = ["open", str(ruta)]
    elif os.name == "nt":
        os.startfile(str(ruta))                      # type: ignore[attr-defined]
        return ""
    else:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return "sin entorno grafico"
        cmd = ["xdg-open", str(ruta)]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except FileNotFoundError:
        return "no hay visor instalado"
    return ""


# --------------------------------------------------------------------------- #
# Acceso a los archivos de la placa (o locales, en prueba)
# --------------------------------------------------------------------------- #
class Archivos:
    """Lista y trae archivos de la placa. En prueba local no copia nada."""

    def __init__(self, ip: str, clave: str | None, cache: Path, base: str):
        self.ip = ip
        self._clave = clave
        self._cache = cache
        self._base = base.rstrip("/")

    def _ssh(self, orden: str, timeout: int = 20) -> tuple[int, str]:
        pre = ["sshpass", "-p", self._clave] if self._clave else []
        cmd = pre + ["ssh", *SSH_OPC, f"root@{self.ip}", orden]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=timeout)
            return r.returncode, r.stdout
        except Exception as exc:                      # noqa: BLE001
            return 1, str(exc)

    def listar(self, subcarpeta: str, extensiones: tuple[str, ...]) -> list[str]:
        """Nombres de archivo, del mas reciente al mas viejo."""
        carpeta = f"{self._base}/{subcarpeta}"
        if es_local(self.ip):
            p = Path(carpeta)
            if not p.is_dir():
                return []
            archivos = [f for f in p.iterdir()
                        if f.is_file() and f.suffix.lower() in extensiones]
            archivos.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            return [f.name for f in archivos]
        rc, salida = self._ssh(f"ls -t {carpeta} 2>/dev/null")
        if rc != 0:
            return []
        return [n for n in salida.split()
                if os.path.splitext(n)[1].lower() in extensiones]

    def traer(self, subcarpeta: str, nombre: str) -> Path | None:
        """Ruta local del archivo, copiandolo de la placa si hace falta."""
        remoto = f"{self._base}/{subcarpeta}/{nombre}"
        if es_local(self.ip):
            p = Path(remoto)
            return p if p.is_file() else None
        destino = self._cache / subcarpeta
        destino.mkdir(parents=True, exist_ok=True)
        local = destino / nombre
        if local.is_file():
            return local
        return self._scp(remoto, local)

    def traer_ruta(self, remoto: str) -> Path | None:
        """Trae un archivo por su ruta absoluta en la placa."""
        if es_local(self.ip):
            p = Path(remoto)
            return p if p.is_file() else None
        self._cache.mkdir(parents=True, exist_ok=True)
        return self._scp(remoto, self._cache / Path(remoto).name)

    def _scp(self, remoto: str, local: Path) -> Path | None:
        pre = ["sshpass", "-p", self._clave] if self._clave else []
        cmd = pre + ["scp", *SSH_OPC, f"root@{self.ip}:{remoto}", str(local)]
        try:
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=60)
        except Exception:                             # noqa: BLE001
            return None
        return local if r.returncode == 0 else None



# --------------------------------------------------------------------------- #
# Recoleccion (CU-2) y borrado de evidencia
# --------------------------------------------------------------------------- #
class Recolector:
    """Corre recolectar-evidencia.sh en segundo plano.

    El script trae la grabacion continua, los clips, la bitacora y los QR de
    las credenciales ACTIVAS, y fusiona los segmentos de 60 s en un unico MP4
    con ffmpeg. Va en un hilo aparte: mientras copia, el vigilante tiene que
    poder seguir resolviendo solicitudes.
    """

    def __init__(self, ip: str, clave: str | None, log):
        self._ip = ip
        self._clave = clave
        self._log = log
        self._hilo: threading.Thread | None = None

    def en_curso(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def lanzar(self) -> None:
        if self.en_curso():
            self._log("ya hay una recoleccion en curso")
            return
        if not SCRIPT_RECOLECTAR.is_file():
            self._log(f"no se encontro {SCRIPT_RECOLECTAR}", "error")
            return
        self._hilo = threading.Thread(target=self._correr, daemon=True)
        self._hilo.start()

    def _correr(self) -> None:
        entorno = dict(os.environ, IP=self._ip)
        if self._clave is not None:
            entorno["CLAVE"] = self._clave
        self._log("recoleccion iniciada (se puede seguir operando)")
        try:
            proc = subprocess.Popen(
                ["bash", str(SCRIPT_RECOLECTAR)], env=entorno,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, errors="replace")
        except OSError as exc:
            self._log(f"no se pudo correr la recoleccion: {exc}", "error")
            return
        assert proc.stdout is not None
        for linea in proc.stdout:
            linea = linea.rstrip("\n")
            if linea:
                self._log(f"[recolectar] {linea}")
        codigo = proc.wait()
        if codigo == 0:
            self._log("recoleccion terminada en ~/recoleccion", "ok")
        else:
            self._log(f"la recoleccion fallo (codigo {codigo})", "error")


class Borrador:
    """Borra en la placa evidencia, clips y bitacora. Las credenciales no.

    Se hace por SSH y no por el canal 5001: asi nadie conectado al canal de
    decisiones puede borrar la evidencia. El servicio se detiene antes, para
    que el segmento en curso se cierre bien, y se rearranca aunque el borrado
    falle, para no dejar la placa sin servicio.
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

    def __init__(self, ip: str, clave: str | None, log):
        self._ip = ip
        self._clave = clave
        self._log = log

    def lanzar(self) -> None:
        threading.Thread(target=self._correr, daemon=True).start()

    def _correr(self) -> None:
        if es_local(self._ip):
            self._log("borrado remoto no disponible en prueba local", "error")
            return
        self._log("borrando en la placa (el servicio se reinicia: la conexion "
                  "se corta unos segundos) ...")
        pre = ["sshpass", "-p", self._clave] if self._clave else []
        try:
            proc = subprocess.run(
                pre + ["ssh", *SSH_OPC, f"root@{self._ip}", self.COMANDO],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                errors="replace", timeout=90)
        except subprocess.TimeoutExpired:
            self._log("el borrado no respondio en 90 s", "error")
            return
        except FileNotFoundError:
            self._log("falta sshpass (solo si la placa pide contrasena)", "error")
            return
        for linea in (proc.stdout + proc.stderr).splitlines():
            if linea.strip():
                self._log(f"[borrar] {linea}")
        c = proc.returncode
        if c == 0:
            self._log("evidencia, eventos y bitacora borrados en la placa", "ok")
        elif c == 10:
            self._log("no se pudo detener el servicio: no se borro nada", "error")
        elif c == 11:
            self._log("se borro, pero el servicio NO volvio a arrancar: revisar "
                      "la placa (systemctl status acceso-control)", "error")
        elif c == 255:
            self._log(f"no se pudo entrar por SSH a root@{self._ip}", "error")
        else:
            self._log(f"el borrado fallo (codigo {c})", "error")


# --------------------------------------------------------------------------- #
# Receptor de video
# --------------------------------------------------------------------------- #
class Receptor:
    CAPS = ("application/x-rtp,media=(string)video,clock-rate=(int)90000,"
            "encoding-name=(string)H264,payload=(int)96")

    def __init__(self, puerto: int, al_fps, al_log):
        self._puerto = puerto
        self._al_fps = al_fps
        self._al_log = al_log
        self._proc: subprocess.Popen | None = None
        self.fps_muestras: list[float] = []

    def abierto(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def abrir(self) -> None:
        if self.abierto():
            self._al_log("la ventana de video ya esta abierta")
            return
        cmd = ["gst-launch-1.0",
               "udpsrc", f"port={self._puerto}", f"caps={self.CAPS}",
               "!", "rtpjitterbuffer", "latency=100",
               "!", "rtph264depay", "!", "h264parse", "!", "avdec_h264",
               "!", "videoconvert",
               # fpsdisplaysink cuenta los cuadros REALMENTE recibidos (RF-1)
               "!", "fpsdisplaysink", "video-sink=autovideosink",
               # text-overlay=false: el contador de rendered/dropped no va
               # encima del video. Los fps se siguen contando y se muestran
               # en la cabecera de la ventana (RF-1).
               "sync=false", "text-overlay=false"]
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT,
                                          text=True, bufsize=1)
        except FileNotFoundError:
            self._al_log("ERROR: falta gst-launch-1.0 (gstreamer1.0-tools)",
                         "error")
            return
        threading.Thread(target=self._leer, daemon=True).start()
        self._al_log(f"video: escuchando en UDP {self._puerto}")

    def _leer(self) -> None:
        assert self._proc and self._proc.stdout
        for linea in self._proc.stdout:
            m = RE_FPS.search(linea)
            if m:
                self.fps_muestras.append(float(m.group(1)))
                self._al_fps(float(m.group(1)), float(m.group(2)))
        self._al_log("la ventana de video se cerro (boton 'Reabrir video')")

    def cerrar(self) -> None:
        if self.abierto():
            self._proc.terminate()                    # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# Canal de comandos
# --------------------------------------------------------------------------- #
class Canal:
    def __init__(self, host: str, puerto: int, al_linea, al_estado):
        self._host, self._puerto = host, puerto
        self._al_linea = al_linea
        self._al_estado = al_estado
        self._sock: socket.socket | None = None
        self._f = None
        self._lock = threading.Lock()
        self._respuestas: queue.Queue = queue.Queue()
        self.rtt_muestras: list[float] = []
        self.al_responder = None            # callback opcional con el texto OK

    def conectar(self) -> bool:
        try:
            self._sock = socket.create_connection((self._host, self._puerto),
                                                  timeout=5)
            # Sin TCP_NODELAY, Nagle mas ACK retardado suman ~40 ms al RTT (RF-3)
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._sock.settimeout(None)
            self._f = self._sock.makefile("rw", encoding="utf-8", newline="\n")
        except OSError as e:
            self._al_linea(f"sin conexion con {self._host}:{self._puerto} ({e})",
                           "error")
            self._al_estado(False)
            return False
        threading.Thread(target=self._leer, daemon=True).start()
        self._al_estado(True)
        return True

    def _leer(self) -> None:
        try:
            for linea in self._f:                     # type: ignore[union-attr]
                linea = linea.rstrip("\n")
                if not linea:
                    continue
                if linea.startswith("EVENTO"):
                    self._al_linea(linea, "evento")
                    continue
                tipo = "ok" if linea.startswith("OK") else (
                    "error" if linea.startswith("ERROR") else "")
                self._respuestas.put(linea)
                self._al_linea(linea, tipo)
                if linea.startswith("OK") and self.al_responder:
                    self.al_responder(linea)
        except Exception as e:                        # noqa: BLE001
            self._al_linea(f"conexion cerrada: {e}", "error")
            self._al_estado(False)

    def enviar(self, comando: str, silencioso: bool = False) -> tuple[str, float]:
        if self._f is None:
            self._al_linea("no hay conexion con la placa", "error")
            return ("", 0.0)
        with self._lock:
            while not self._respuestas.empty():
                self._respuestas.get_nowait()
            if not silencioso:
                self._al_linea(f"> {comando}")
            t0 = time.perf_counter()
            try:
                self._f.write(comando + "\n")
                self._f.flush()
                resp = self._respuestas.get(timeout=8)
            except Exception as e:                    # noqa: BLE001
                self._al_linea(f"sin respuesta: {e}", "error")
                return ("", 0.0)
            rtt = (time.perf_counter() - t0) * 1000
        self.rtt_muestras.append(rtt)
        return (resp, rtt)

    def cerrar(self) -> None:
        try:
            if self._sock:
                self._sock.close()
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Galeria de miniaturas
# --------------------------------------------------------------------------- #
class Galeria(ttk.Frame):
    """Rejilla de archivos. Doble clic abre con el visor del sistema."""

    COLUMNAS = 4
    LADO = 150

    def __init__(self, padre, archivos: Archivos, subcarpeta: str,
                 extensiones: tuple[str, ...], log, con_miniatura: bool):
        super().__init__(padre, padding=10)
        self._archivos = archivos
        self._sub = subcarpeta
        self._ext = extensiones
        self._log = log
        self._con_miniatura = con_miniatura
        self._imagenes: list[tk.PhotoImage] = []      # sin esto el GC las borra
        self._tmp = Path(".cache-miniaturas")

        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Button(barra, text="Actualizar", command=self.refrescar).pack(side="left")
        self._lbl = ttk.Label(barra, text="", foreground=COLOR_TENUE)
        self._lbl.pack(side="left", padx=12)
        ttk.Label(barra, text="doble clic para abrir",
                  foreground=COLOR_TENUE).pack(side="right")

        self._lienzo = tk.Canvas(self, highlightthickness=0)
        barra_v = ttk.Scrollbar(self, orient="vertical", command=self._lienzo.yview)
        self._interior = ttk.Frame(self._lienzo)
        self._interior.bind("<Configure>", lambda e: self._lienzo.configure(
            scrollregion=self._lienzo.bbox("all")))
        self._lienzo.create_window((0, 0), window=self._interior, anchor="nw")
        self._lienzo.configure(yscrollcommand=barra_v.set)
        self._lienzo.pack(side="left", fill="both", expand=True)
        barra_v.pack(side="right", fill="y")

    def refrescar(self) -> None:
        threading.Thread(target=self._cargar, daemon=True).start()

    def _cargar(self) -> None:
        nombres = self._archivos.listar(self._sub, self._ext)
        self.after(0, lambda: self._pintar(nombres))

    def _pintar(self, nombres: list[str]) -> None:
        for w in self._interior.winfo_children():
            w.destroy()
        self._imagenes.clear()
        self._lbl.config(text=f"{len(nombres)} archivos")
        if not nombres:
            ttk.Label(self._interior, text="(sin archivos todavia)",
                      foreground=COLOR_TENUE).grid(row=0, column=0, padx=10, pady=10)
            return
        for i, nombre in enumerate(nombres[:40]):
            fila, col = divmod(i, self.COLUMNAS)
            celda = ttk.Frame(self._interior, padding=6)
            celda.grid(row=fila, column=col, sticky="n")
            if self._con_miniatura:
                cuadro = tk.Label(celda, text="cargando…", width=20, height=9,
                                  relief="groove", bg="#f3f0ea")
            else:
                cuadro = tk.Label(celda, text="▶", font=("TkDefaultFont", 30),
                                  width=7, height=3, relief="groove", bg="#f3f0ea")
            cuadro.pack()
            ttk.Label(celda, text=nombre[:26], font=("TkDefaultFont", 8),
                      foreground=COLOR_TENUE).pack()
            cuadro.bind("<Double-Button-1>", lambda e, n=nombre: self._abrir(n))
            if self._con_miniatura:
                threading.Thread(target=self._miniatura, args=(nombre, cuadro),
                                 daemon=True).start()

    def _miniatura(self, nombre: str, etiqueta: tk.Label) -> None:
        ruta = self._archivos.traer(self._sub, nombre)
        if ruta is None or cv2 is None:
            self.after(0, lambda: etiqueta.config(text=nombre[:16]))
            return
        img = cv2.imread(str(ruta))
        if img is None:
            self.after(0, lambda: etiqueta.config(text="(ilegible)"))
            return
        alto, ancho = img.shape[:2]
        escala = self.LADO / max(alto, ancho)
        chica = cv2.resize(img, (int(ancho * escala), int(alto * escala)),
                           interpolation=cv2.INTER_AREA)
        # Tk no lee BMP: se convierte a PNG, que si entiende desde 8.6
        self._tmp.mkdir(exist_ok=True)
        png = self._tmp / (Path(nombre).stem + ".png")
        cv2.imwrite(str(png), chica)

        def mostrar():
            try:
                foto = tk.PhotoImage(file=str(png))
                self._imagenes.append(foto)
                etiqueta.config(image=foto, text="",
                                width=chica.shape[1], height=chica.shape[0])
            except tk.TclError:
                etiqueta.config(text=nombre[:16])
        self.after(0, mostrar)

    def _abrir(self, nombre: str) -> None:
        def correr():
            ruta = self._archivos.traer(self._sub, nombre)
            if ruta is None:
                self._log(f"no se pudo traer {nombre}", "error")
                return
            err = abrir_con_el_sistema(ruta)
            self._log(err or f"abriendo {ruta}", "error" if err else "")
        threading.Thread(target=correr, daemon=True).start()


# --------------------------------------------------------------------------- #
# Ventana principal
# --------------------------------------------------------------------------- #
class Aplicacion:
    def __init__(self, ip: str, clave: str | None, base: str, sin_video: bool):
        self.ip = ip
        self.raiz = tk.Tk()
        self.raiz.title(f"Puesto de vigilancia — {ip}")
        self.raiz.geometry("980x700")

        self.archivos = Archivos(ip, clave, Path("recibidos"), base)
        self.canal = Canal(ip, PUERTO_TCP, self.log, self._estado_conexion)
        self.canal.al_responder = self._quizas_abrir_credencial
        self.receptor = Receptor(PUERTO_RTP, self._mostrar_fps, self.log)
        self.recolector = Recolector(ip, clave, self.log)
        self.borrador = Borrador(ip, clave, self.log)
        self._sin_video = sin_video

        self._construir()
        self.raiz.protocol("WM_DELETE_WINDOW", self._salir)

    # ------------------------------------------------------------------ #
    def _construir(self) -> None:
        cab = ttk.Frame(self.raiz, padding=(12, 8))
        cab.pack(fill="x")
        self.lbl_estado = tk.Label(cab, text="● desconectado", fg=COLOR_TENUE,
                                   font=("TkDefaultFont", 11, "bold"))
        self.lbl_estado.pack(side="left")
        self.lbl_fps = tk.Label(cab, text="fps: —", font=("TkFixedFont", 10))
        self.lbl_fps.pack(side="left", padx=16)
        self.lbl_rtt = tk.Label(cab, text="RTT: —", font=("TkFixedFont", 10))
        self.lbl_rtt.pack(side="left", padx=16)
        ttk.Button(cab, text="Reabrir video",
                   command=self.receptor.abrir).pack(side="right")

        libretas = ttk.Notebook(self.raiz)
        libretas.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        libretas.add(self._pestana_operacion(libretas), text="  Operación  ")
        libretas.add(self._pestana_credenciales(libretas), text="  Credenciales  ")

        self.galeria_qr = Galeria(libretas, self.archivos, "credenciales",
                                  EXT_IMAGEN, self.log, con_miniatura=True)
        libretas.add(self.galeria_qr, text="  Galería de QR  ")

        self.galeria_clips = Galeria(libretas, self.archivos, "eventos",
                                     (".mp4",), self.log, con_miniatura=False)
        libretas.add(self.galeria_clips, text="  Clips de eventos  ")

        libretas.add(self._pestana_evidencia(libretas), text="  Evidencia  ")
        libretas.add(self._pestana_mediciones(libretas), text="  Mediciones  ")

        self.txt = tk.Text(self.raiz, height=9, font=("TkFixedFont", 9),
                           wrap="word")
        self.txt.pack(fill="both", padx=12, pady=(0, 12))
        for tipo, color in (("ok", COLOR_OK), ("error", COLOR_ERR),
                            ("evento", "#8a6200")):
            self.txt.tag_config(tipo, foreground=color)

    # ------------------------------------------------------------------ #
    def _pestana_operacion(self, padre) -> ttk.Frame:
        f = ttk.Frame(padre, padding=16)
        ttk.Label(f, text="Solicitud de acceso",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(f, text="El visitante pide entrar y el vigilante decide dentro "
                          "del plazo configurado. Al vencerse, se deniega (RF-6).",
                  foreground=COLOR_TENUE).pack(anchor="w", pady=(0, 12))

        fila = ttk.Frame(f)
        fila.pack(anchor="w", pady=4)
        ttk.Button(fila, text="SOLICITUD", width=16,
                   command=lambda: self._enviar("SOLICITUD")).pack(side="left", padx=4)
        ttk.Button(fila, text="ESTADO", width=16,
                   command=lambda: self._enviar("ESTADO")).pack(side="left", padx=4)

        fila2 = ttk.Frame(f)
        fila2.pack(anchor="w", pady=14)
        tk.Button(fila2, text="PERMITIR", width=18, height=2, bg="#cde8d0",
                  font=("TkDefaultFont", 11, "bold"),
                  command=lambda: self._enviar("PERMITIR")).pack(side="left", padx=4)
        tk.Button(fila2, text="DENEGAR", width=18, height=2, bg="#efcccc",
                  font=("TkDefaultFont", 11, "bold"),
                  command=lambda: self._enviar("DENEGAR")).pack(side="left", padx=4)

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=16)
        ttk.Button(f, text="Comando libre…", width=18,
                   command=self._libre).pack(anchor="w")
        return f

    def _pestana_credenciales(self, padre) -> ttk.Frame:
        f = ttk.Frame(padre, padding=16)
        ttk.Label(f, text="Alta de credencial",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(f, text="El rol «vigilante» no está en la lista: el vigilante "
                          "opera este puesto y decide los accesos, no se "
                          "identifica con un QR en la puerta.",
                  foreground=COLOR_TENUE, wraplength=840).pack(anchor="w",
                                                               pady=(0, 14))

        fila = ttk.Frame(f)
        fila.pack(anchor="w", pady=4)
        ttk.Label(fila, text="Nombre:").pack(side="left")
        self.ent_nombre = ttk.Entry(fila, width=32)
        self.ent_nombre.pack(side="left", padx=6)
        self.ent_nombre.bind("<Return>", lambda e: self._alta())
        ttk.Label(fila, text="Rol:").pack(side="left", padx=(14, 0))
        self.cmb_rol = ttk.Combobox(fila, values=list(ROLES_CON_QR), width=16,
                                    state="readonly")
        self.cmb_rol.current(1)
        self.cmb_rol.pack(side="left", padx=6)
        ttk.Button(fila, text="Generar credencial",
                   command=self._alta).pack(side="left", padx=12)

        ttk.Label(f, text="La imagen se trae a esta computadora y se abre sola, "
                          "lista para compartir o imprimir.",
                  foreground=COLOR_TENUE).pack(anchor="w", pady=(10, 18))

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=8)
        fila2 = ttk.Frame(f)
        fila2.pack(anchor="w", pady=10)
        ttk.Button(fila2, text="LISTAR activas", width=18,
                   command=lambda: self._enviar("LISTAR")).pack(side="left", padx=4)
        ttk.Button(fila2, text="Revocar (BAJA)…", width=18,
                   command=self._baja).pack(side="left", padx=4)
        ttk.Button(fila2, text="REGENERAR_QR", width=18,
                   command=self._regenerar).pack(side="left", padx=4)
        return f


    def _pestana_evidencia(self, padre) -> ttk.Frame:
        f = ttk.Frame(padre, padding=16)
        ttk.Label(f, text="Extracción de evidencia (CU-2)",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(f, text="Trae de la placa la grabación continua, los clips de "
                          "cada evento, la bitácora y los QR de las credenciales "
                          "activas. Fusiona los segmentos de 60 s en un único MP4 "
                          "(requiere ffmpeg). Todo queda en ~/recolección.",
                  foreground=COLOR_TENUE, wraplength=840).pack(anchor="w",
                                                               pady=(0, 14))
        ttk.Button(f, text="RECOLECTAR", width=24,
                   command=self.recolector.lanzar).pack(anchor="w", pady=4)

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=18)
        ttk.Label(f, text="Borrado en la placa",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(f, text="Borra evidencia, clips y bitácora EN LA PLACA. Las "
                          "credenciales no se tocan. El servicio se detiene y se "
                          "rearranca solo, así que el video se corta unos segundos.",
                  foreground=COLOR_TENUE, wraplength=840).pack(anchor="w",
                                                               pady=(0, 12))
        tk.Button(f, text="BORRAR evidencia y bitácora", width=30, bg="#efcccc",
                  command=self._borrar).pack(anchor="w", pady=4)
        return f

    def _borrar(self) -> None:
        if messagebox.askyesno(
                "Borrar en la placa",
                "Se borran en la placa:\n"
                "  • la grabación continua (evidencia/)\n"
                "  • los clips de eventos (eventos/)\n"
                "  • la bitácora de accesos\n\n"
                "Las credenciales NO se tocan.\n"
                "El servicio se reinicia.\n\n¿Continuar?",
                icon="warning"):
            self.borrador.lanzar()
            self.raiz.after(8000, self.galeria_clips.refrescar)

    def _pestana_mediciones(self, padre) -> ttk.Frame:
        f = ttk.Frame(padre, padding=16)
        ttk.Label(f, text="Verificación de requisitos",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(f, text="RF-1  ≥ 15 fps recibidos en esta computadora. Se cuenta "
                          "solo, con la ventana de video abierta.\n"
                          "RF-3  comando detectado en ≤ 100 ms.",
                  foreground=COLOR_TENUE).pack(anchor="w", pady=(0, 16))
        ttk.Button(f, text="RF-3: medir RTT (20 PING)", width=30,
                   command=self._medir_rtt).pack(anchor="w", pady=4)
        ttk.Button(f, text="Guardar evidencia a archivo", width=30,
                   command=self._guardar).pack(anchor="w", pady=4)
        return f

    # ------------------------------------------------------------------ #
    def log(self, texto: str, tipo: str = "") -> None:
        def escribir():
            self.txt.insert("end", f"[{datetime.now():%H:%M:%S}] {texto}\n", tipo)
            self.txt.see("end")
        try:
            self.raiz.after(0, escribir)
        except RuntimeError:
            pass

    def _estado_conexion(self, conectado: bool) -> None:
        self.lbl_estado.config(text="● conectado" if conectado else "● desconectado",
                               fg=COLOR_OK if conectado else COLOR_ERR)

    def _mostrar_fps(self, actual: float, promedio: float) -> None:
        self.lbl_fps.config(text=f"fps: {actual:5.2f} (prom {promedio:5.2f})")

    def _enviar(self, comando: str) -> None:
        def correr():
            _, rtt = self.canal.enviar(comando)
            if rtt:
                self.lbl_rtt.config(text=f"RTT: {rtt:.1f} ms")
        threading.Thread(target=correr, daemon=True).start()

    # ------------------------------------------------------------------ #
    def _alta(self) -> None:
        nombre = self.ent_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Alta", "Falta el nombre.")
            return
        self.ent_nombre.delete(0, "end")
        self._enviar(f"ALTA {self.cmb_rol.get()} {nombre}")

    def _baja(self) -> None:
        ident = simpledialog.askstring(
            "Revocar credencial",
            "Identificador a revocar (se ve con LISTAR):", parent=self.raiz)
        if ident:
            self._enviar(f"BAJA {ident.strip()}")

    def _regenerar(self) -> None:
        if messagebox.askyesno(
                "REGENERAR_QR",
                "Rehace las imágenes de las credenciales activas.\n"
                "Los identificadores no cambian: un QR impreso antes sigue "
                "valiendo.\n\n¿Continuar?"):
            self._enviar("REGENERAR_QR")
            self.raiz.after(2500, self.galeria_qr.refrescar)

    def _libre(self) -> None:
        cmd = simpledialog.askstring("Comando libre", "Comando:", parent=self.raiz)
        if cmd:
            self._enviar(cmd.strip())

    def _quizas_abrir_credencial(self, linea: str) -> None:
        """La respuesta de ALTA trae la ruta: se trae la imagen y se abre."""
        m = RE_RUTA_CRED.search(linea)
        if not m:
            return

        def correr():
            ruta = self.archivos.traer_ruta(m.group(1))
            if ruta is None:
                self.log(f"no se pudo traer {m.group(1)}", "error")
                return
            err = abrir_con_el_sistema(ruta)
            self.log(err or f"credencial abierta: {ruta}", "error" if err else "ok")
            self.raiz.after(0, self.galeria_qr.refrescar)
        threading.Thread(target=correr, daemon=True).start()

    # ------------------------------------------------------------------ #
    def _medir_rtt(self) -> None:
        def correr():
            self.log("RF-3: enviando 20 PING…")
            m = []
            for _ in range(20):
                _, rtt = self.canal.enviar("PING", silencioso=True)
                if rtt:
                    m.append(rtt)
                time.sleep(0.15)
            if not m:
                self.log("sin respuestas", "error")
                return
            m.sort()
            p50 = m[len(m) // 2]
            p95 = m[min(len(m) - 1, int(len(m) * 0.95))]
            cumple = m[-1] <= 100
            self.log(f"RF-3  n={len(m)}  min={m[0]:.1f}  p50={p50:.1f}  "
                     f"p95={p95:.1f}  max={m[-1]:.1f} ms")
            self.log(f"RF-3  criterio ≤ 100 ms: "
                     f"{'CUMPLE' if cumple else 'NO CUMPLE'}",
                     "ok" if cumple else "error")
            self.lbl_rtt.config(text=f"RTT p50: {p50:.1f} ms")
        threading.Thread(target=correr, daemon=True).start()

    def _guardar(self) -> None:
        ruta = Path(f"evidencia-vigilancia-{datetime.now():%Y%m%d-%H%M%S}.txt")
        fps, rtt = self.receptor.fps_muestras, self.canal.rtt_muestras
        with ruta.open("w", encoding="utf-8") as f:
            f.write("# Puesto de vigilancia — evidencia RF-1 y RF-3\n")
            f.write(f"# placa: {self.ip}   {datetime.now().isoformat()}\n\n")
            f.write("== RF-1: cuadros por segundo recibidos en el puesto ==\n")
            if fps:
                f.write(f"muestras : {len(fps)}\n"
                        f"minimo   : {min(fps):.2f} fps\n"
                        f"promedio : {sum(fps)/len(fps):.2f} fps\n"
                        f"maximo   : {max(fps):.2f} fps\n"
                        f"criterio >= 15 fps : "
                        f"{'CUMPLE' if min(fps) >= 15 else 'NO CUMPLE'}\n")
            else:
                f.write("sin muestras (ventana de video cerrada)\n")
            f.write("\n== RF-3: tiempo de ida y vuelta de los comandos ==\n")
            if rtt:
                o = sorted(rtt)
                f.write(f"muestras : {len(o)}\n"
                        f"minimo   : {o[0]:.1f} ms\n"
                        f"p50      : {o[len(o)//2]:.1f} ms\n"
                        f"maximo   : {o[-1]:.1f} ms\n"
                        f"criterio <= 100 ms : "
                        f"{'CUMPLE' if o[-1] <= 100 else 'NO CUMPLE'}\n")
            else:
                f.write("sin muestras\n")
            f.write("\n== Transcripcion de la sesion ==\n")
            f.write(self.txt.get("1.0", "end"))
        self.log(f"evidencia guardada en {ruta.resolve()}", "ok")

    # ------------------------------------------------------------------ #
    def _salir(self) -> None:
        self.receptor.cerrar()
        self.canal.cerrar()
        shutil.rmtree(".cache-miniaturas", ignore_errors=True)
        self.raiz.destroy()

    def correr(self) -> None:
        self.log(f"puesto de vigilancia — placa {self.ip}")
        if not self._sin_video:
            self.receptor.abrir()
        # Al conectarse, la placa redirige el video a esta IP: el receptor
        # tiene que estar escuchando antes.
        self.raiz.after(900, self._conectar_y_cargar)
        self.raiz.mainloop()

    def _conectar_y_cargar(self) -> None:
        if self.canal.conectar():
            self.galeria_qr.refrescar()
            self.galeria_clips.refrescar()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Puesto de vigilancia con interfaz grafica")
    ap.add_argument("--ip", default="172.21.255.55", help="IP de la placa")
    ap.add_argument("--clave", default=os.environ.get("CLAVE"),
                    help="contrasena de root en la placa (requiere sshpass)")
    ap.add_argument("--base", default=None,
                    help=f"carpeta de datos (por omision {REMOTO}; en prueba "
                         "local, ~/acceso-local)")
    ap.add_argument("--sin-video", action="store_true",
                    help="no abrir la ventana del video")
    args = ap.parse_args()

    base = args.base or (os.path.expanduser("~/acceso-local")
                         if es_local(args.ip) else REMOTO)
    Aplicacion(args.ip, args.clave, base, args.sin_video).correr()
    return 0


if __name__ == "__main__":
    sys.exit(main())
