#!/usr/bin/env python3
"""Puesto de vigilancia unificado (CU-1, CU-3, CU-11, CU-12).

Una sola terminal: abre el video RTP en vivo y un panel con los comandos.
Sustituye a receptor-vigilancia.sh + telnet/nc + consola de credenciales.

    python3 puesto-vigilancia.py <IP-de-la-placa>

Mide ademas, sin trabajo extra:
  * RF-1: cuadros por segundo recibidos (fpsdisplaysink en el receptor)
  * RF-3: tiempo de ida y vuelta de cada comando (RTT)

Requisitos en la computadora del vigilante:
  gstreamer1.0-tools, gstreamer1.0-plugins-good/bad/libav, python3-tk
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import scrolledtext, simpledialog
except ImportError:
    sys.exit("Falta python3-tk.  sudo apt install python3-tk")

PUERTO_RTP = 5000
PUERTO_TCP = 5001

# El patron que imprime fpsdisplaysink: "...current: 29.70, average: 29.68..."
RE_FPS = re.compile(r"current:\s*([0-9.]+).*?average:\s*([0-9.]+)")


# --------------------------------------------------------------------------- #
# Receptor de video
# --------------------------------------------------------------------------- #
class Receptor:
    """Lanza gst-launch-1.0 en su propia ventana y lee su salida de fps."""

    CAPS = ("application/x-rtp,media=(string)video,clock-rate=(int)90000,"
            "encoding-name=(string)H264,payload=(int)96")

    def __init__(self, puerto: int, al_fps, al_log):
        self._puerto = puerto
        self._al_fps = al_fps
        self._al_log = al_log
        self._proc: subprocess.Popen | None = None
        self.fps_muestras: list[float] = []

    def iniciar(self) -> None:
        cmd = [
            "gst-launch-1.0",
            "udpsrc", f"port={self._puerto}", f"caps={self.CAPS}",
            "!", "rtpjitterbuffer", "latency=100",
            "!", "rtph264depay", "!", "h264parse", "!", "avdec_h264",
            "!", "videoconvert",
            # fpsdisplaysink cuenta los cuadros REALES recibidos (RF-1)
            "!", "fpsdisplaysink", "video-sink=autovideosink", "sync=false",
            "text-overlay=true",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
        except FileNotFoundError:
            self._al_log("ERROR: no se encontro gst-launch-1.0. "
                         "Instalar gstreamer1.0-tools.")
            return
        threading.Thread(target=self._leer, daemon=True).start()
        self._al_log(f"receptor RTP escuchando en UDP {self._puerto}")

    def _leer(self) -> None:
        assert self._proc and self._proc.stdout
        for linea in self._proc.stdout:
            m = RE_FPS.search(linea)
            if m:
                actual, promedio = float(m.group(1)), float(m.group(2))
                self.fps_muestras.append(actual)
                self._al_fps(actual, promedio)
            elif "ERROR" in linea:
                self._al_log(linea.rstrip())

    def detener(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


# --------------------------------------------------------------------------- #
# Canal de comandos
# --------------------------------------------------------------------------- #
class Canal:
    """Cliente TCP del servidor de decisiones de la placa."""

    def __init__(self, host: str, puerto: int, al_linea, al_estado):
        self._host, self._puerto = host, puerto
        self._al_linea = al_linea
        self._al_estado = al_estado
        self._sock: socket.socket | None = None
        self._f = None
        self._lock = threading.Lock()
        self._respuestas: queue.Queue = queue.Queue()
        self.rtt_muestras: list[float] = []

    def conectar(self) -> bool:
        try:
            self._sock = socket.create_connection((self._host, self._puerto), timeout=5)
            # Sin TCP_NODELAY, Nagle + ACK retardado agregan ~40 ms (RF-3)
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._sock.settimeout(None)
            self._f = self._sock.makefile("rw", encoding="utf-8", newline="\n")
        except OSError as e:
            self._al_linea(f"ERROR conectando a {self._host}:{self._puerto} -> {e}")
            self._al_estado(False)
            return False
        threading.Thread(target=self._leer, daemon=True).start()
        self._al_linea(f"conectado a {self._host}:{self._puerto}")
        self._al_estado(True)
        return True

    def _leer(self) -> None:
        try:
            for linea in self._f:
                linea = linea.rstrip("\n")
                if not linea:
                    continue
                if linea.startswith("EVENTO"):
                    self._al_linea(f"<< {linea}")
                else:
                    self._respuestas.put(linea)
                    self._al_linea(f"<< {linea}")
        except Exception as e:
            self._al_linea(f"conexion cerrada: {e}")
            self._al_estado(False)

    def enviar(self, comando: str) -> tuple[str, float]:
        """Envia un comando y devuelve (respuesta, RTT en ms)."""
        if self._f is None:
            self._al_linea("no hay conexion")
            return ("", 0.0)
        with self._lock:
            while not self._respuestas.empty():
                self._respuestas.get_nowait()
            self._al_linea(f">> {comando}")
            t0 = time.perf_counter()
            try:
                self._f.write(comando + "\n")
                self._f.flush()
                resp = self._respuestas.get(timeout=5)
            except Exception as e:
                self._al_linea(f"sin respuesta: {e}")
                return ("", 0.0)
            rtt = (time.perf_counter() - t0) * 1000
        self.rtt_muestras.append(rtt)
        self._al_linea(f"   RTT = {rtt:.1f} ms")
        return (resp, rtt)

    def cerrar(self) -> None:
        try:
            if self._sock:
                self._sock.close()
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Interfaz
# --------------------------------------------------------------------------- #
class Panel:
    def __init__(self, host: str):
        self.host = host
        self.raiz = tk.Tk()
        self.raiz.title(f"Puesto de vigilancia  —  {host}")
        self.raiz.geometry("760x560")

        self.canal = Canal(host, PUERTO_TCP, self.log, self._marcar_estado)
        self.receptor = Receptor(PUERTO_RTP, self._mostrar_fps, self.log)

        self._construir()
        self.raiz.protocol("WM_DELETE_WINDOW", self._salir)

    # ----------------------------------------------------------------- #
    def _construir(self) -> None:
        cab = tk.Frame(self.raiz, pady=6)
        cab.pack(fill="x")
        self.lbl_estado = tk.Label(cab, text="● desconectado", fg="#999",
                                   font=("TkDefaultFont", 11, "bold"))
        self.lbl_estado.pack(side="left", padx=10)
        self.lbl_fps = tk.Label(cab, text="fps: —", font=("TkFixedFont", 11))
        self.lbl_fps.pack(side="left", padx=10)
        self.lbl_rtt = tk.Label(cab, text="RTT: —", font=("TkFixedFont", 11))
        self.lbl_rtt.pack(side="left", padx=10)

        # --- Decisiones de acceso (CU-3) ---
        f1 = tk.LabelFrame(self.raiz, text=" Solicitud de acceso ", padx=8, pady=8)
        f1.pack(fill="x", padx=10, pady=4)
        tk.Button(f1, text="SOLICITUD", width=13,
                  command=lambda: self.canal.enviar("SOLICITUD")).pack(side="left", padx=4)
        tk.Button(f1, text="PERMITIR", width=13, bg="#cde8d0",
                  command=lambda: self.canal.enviar("PERMITIR")).pack(side="left", padx=4)
        tk.Button(f1, text="DENEGAR", width=13, bg="#efcccc",
                  command=lambda: self.canal.enviar("DENEGAR")).pack(side="left", padx=4)
        tk.Button(f1, text="ESTADO", width=13,
                  command=lambda: self.canal.enviar("ESTADO")).pack(side="left", padx=4)

        # --- Credenciales (CU-11, CU-12) ---
        f2 = tk.LabelFrame(self.raiz, text=" Credenciales ", padx=8, pady=8)
        f2.pack(fill="x", padx=10, pady=4)
        tk.Button(f2, text="LISTAR", width=13,
                  command=lambda: self.canal.enviar("LISTAR")).pack(side="left", padx=4)
        tk.Button(f2, text="ALTA…", width=13,
                  command=self._alta).pack(side="left", padx=4)
        tk.Button(f2, text="BAJA…", width=13,
                  command=self._baja).pack(side="left", padx=4)
        tk.Button(f2, text="REGENERAR_QR", width=14,
                  command=lambda: self.canal.enviar("REGENERAR_QR")).pack(side="left", padx=4)

        # --- Mediciones (RF-1, RF-3) ---
        f3 = tk.LabelFrame(self.raiz, text=" Mediciones ", padx=8, pady=8)
        f3.pack(fill="x", padx=10, pady=4)
        tk.Button(f3, text="RF-3: 20 PING (RTT)", width=20,
                  command=self._medir_rtt).pack(side="left", padx=4)
        tk.Button(f3, text="Guardar evidencia", width=18,
                  command=self._guardar).pack(side="left", padx=4)
        tk.Button(f3, text="Comando libre…", width=16,
                  command=self._libre).pack(side="left", padx=4)

        self.txt = scrolledtext.ScrolledText(self.raiz, height=18,
                                             font=("TkFixedFont", 9))
        self.txt.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    # ----------------------------------------------------------------- #
    def log(self, texto: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt.insert("end", f"[{ts}] {texto}\n")
        self.txt.see("end")

    def _marcar_estado(self, conectado: bool) -> None:
        if conectado:
            self.lbl_estado.config(text="● conectado", fg="#2f6b3f")
        else:
            self.lbl_estado.config(text="● desconectado", fg="#8a3324")

    def _mostrar_fps(self, actual: float, promedio: float) -> None:
        self.lbl_fps.config(text=f"fps: {actual:5.2f}  (prom {promedio:5.2f})")

    # ----------------------------------------------------------------- #
    def _alta(self) -> None:
        ident = simpledialog.askstring("ALTA", "Identificador:", parent=self.raiz)
        if not ident:
            return
        nombre = simpledialog.askstring("ALTA", "Nombre completo:", parent=self.raiz)
        rol = simpledialog.askstring("ALTA", "Rol (vigilante/mantenimiento/visitante):",
                                     parent=self.raiz)
        if nombre and rol:
            self.canal.enviar(f"ALTA {ident} {rol} {nombre}")

    def _baja(self) -> None:
        ident = simpledialog.askstring("BAJA", "Identificador a revocar:",
                                       parent=self.raiz)
        if ident:
            self.canal.enviar(f"BAJA {ident}")

    def _libre(self) -> None:
        cmd = simpledialog.askstring("Comando libre", "Comando:", parent=self.raiz)
        if cmd:
            self.canal.enviar(cmd)

    def _medir_rtt(self) -> None:
        """RF-3: 20 PING seguidos. PING no toca el estado de la solicitud."""
        def correr():
            muestras = []
            for _ in range(20):
                _, rtt = self.canal.enviar("PING")
                if rtt:
                    muestras.append(rtt)
                time.sleep(0.2)
            if not muestras:
                return
            muestras.sort()
            n = len(muestras)
            p50 = muestras[n // 2]
            p95 = muestras[min(n - 1, int(n * 0.95))]
            self.log("=" * 52)
            self.log(f"RF-3  n={n}  min={muestras[0]:.1f}  p50={p50:.1f}  "
                     f"p95={p95:.1f}  max={muestras[-1]:.1f} ms")
            self.log(f"RF-3  criterio RTT <= 100 ms : "
                     f"{'CUMPLE' if muestras[-1] <= 100 else 'NO CUMPLE'}")
            self.log("=" * 52)
            self.lbl_rtt.config(text=f"RTT p50: {p50:.1f} ms")
        threading.Thread(target=correr, daemon=True).start()

    def _guardar(self) -> None:
        ruta = f"evidencia-vigilancia-{datetime.now():%Y%m%d-%H%M%S}.txt"
        fps = self.receptor.fps_muestras
        rtt = self.canal.rtt_muestras
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(f"# Puesto de vigilancia — evidencia RF-1 y RF-3\n")
            f.write(f"# placa: {self.host}   {datetime.now().isoformat()}\n\n")
            f.write("== RF-1: cuadros por segundo RECIBIDOS en el puesto ==\n")
            if fps:
                f.write(f"muestras : {len(fps)}\n")
                f.write(f"minimo   : {min(fps):.2f} fps\n")
                f.write(f"promedio : {sum(fps)/len(fps):.2f} fps\n")
                f.write(f"maximo   : {max(fps):.2f} fps\n")
                f.write(f"criterio >= 15 fps : "
                        f"{'CUMPLE' if min(fps) >= 15 else 'NO CUMPLE'}\n")
            else:
                f.write("sin muestras\n")
            f.write("\n== RF-3: RTT de los comandos ==\n")
            if rtt:
                o = sorted(rtt)
                f.write(f"muestras : {len(o)}\n")
                f.write(f"minimo   : {o[0]:.1f} ms\n")
                f.write(f"p50      : {o[len(o)//2]:.1f} ms\n")
                f.write(f"maximo   : {o[-1]:.1f} ms\n")
                f.write(f"criterio <= 100 ms : "
                        f"{'CUMPLE' if o[-1] <= 100 else 'NO CUMPLE'}\n")
            else:
                f.write("sin muestras\n")
            f.write("\n== Transcripcion de la sesion ==\n")
            f.write(self.txt.get("1.0", "end"))
        self.log(f"evidencia guardada en {os.path.abspath(ruta)}")

    # ----------------------------------------------------------------- #
    def _salir(self) -> None:
        self.receptor.detener()
        self.canal.cerrar()
        self.raiz.destroy()

    def correr(self) -> None:
        self.log("Puesto de vigilancia iniciado")
        self.receptor.iniciar()
        # La placa redirige la transmision a quien se conecta al TCP, asi que
        # el receptor tiene que estar escuchando ANTES de conectarse.
        self.raiz.after(800, self.canal.conectar)
        self.raiz.mainloop()


def main() -> None:
    ap = argparse.ArgumentParser(description="Puesto de vigilancia unificado")
    ap.add_argument("host", help="IP de la Raspberry Pi")
    args = ap.parse_args()
    Panel(args.host).correr()


if __name__ == "__main__":
    main()
