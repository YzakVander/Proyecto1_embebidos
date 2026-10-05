"""Registro de credenciales: quien tiene acceso y con que rol (CU-11, CU-12).

El QR lleva SOLO un identificador opaco (ACC-7F3A91). El nombre y el rol
viven aqui, en la placa. Dos consecuencias:

  * Una foto del QR no revela datos personales de nadie.
  * Dar de baja invalida la credencial de inmediato, aunque la imagen impresa
    siga circulando: el identificador deja de resolver a una persona.

Formato: JSON con fsync, igual que la bitacora. Sobrevive a un corte de
energia, no solo a un cierre ordenado, y se inspecciona con cat.

Roles
-----
  vigilante      acceso automatico; ademas opera el puesto de vigilancia
  mantenimiento  acceso automatico (incluye administrador del sistema)
  visitante      requiere confirmacion del vigilante (CU-3)

Un identificador NO registrado tampoco se deniega de entrada: escala al
vigilante igual que un visitante, pero se anota distinto en la bitacora.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum

log = logging.getLogger(__name__)


class Rol(str, Enum):
    VIGILANTE = "vigilante"
    MANTENIMIENTO = "mantenimiento"
    VISITANTE = "visitante"

    @classmethod
    def desde_texto(cls, texto: str) -> "Rol":
        t = texto.strip().lower()
        for r in cls:
            if r.value == t:
                return r
        raise ValueError(
            f"rol desconocido '{texto}'; validos: {', '.join(r.value for r in cls)}"
        )

    def acceso_automatico(self) -> bool:
        """True si el rol entra sin intervencion del vigilante."""
        return self in (Rol.VIGILANTE, Rol.MANTENIMIENTO)


@dataclass
class Credencial:
    identificador: str
    nombre: str
    rol: str
    alta: str                       # ISO-8601 del registro
    activa: bool = True
    baja: str | None = None         # ISO-8601 de la revocacion
    notas: str | None = None

    def rol_enum(self) -> Rol:
        return Rol.desde_texto(self.rol)


def _ahora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def nuevo_identificador(prefijo: str = "ACC") -> str:
    """Identificador opaco, corto y legible: ACC-7F3A91.

    secrets y no random: aunque no sea un secreto criptografico, un
    identificador predecible permitiria fabricar credenciales validas
    probando valores consecutivos.
    """
    return f"{prefijo}-{secrets.token_hex(3).upper()}"


class RegistroCredenciales:
    """Altas, bajas y consulta. Seguro para uso concurrente.

    La baja NO borra el registro: lo marca inactivo y guarda la fecha. Un
    control de acceso tiene que poder responder "quien tenia acceso el
    martes", y eso se pierde si los registros se eliminan.
    """

    def __init__(self, ruta: str) -> None:
        self._ruta = ruta
        self._lock = threading.Lock()
        self._creds: dict[str, Credencial] = {}
        directorio = os.path.dirname(ruta)
        if directorio:
            os.makedirs(directorio, exist_ok=True)
        self._cargar()
        log.info("registro de credenciales: %s (%d activas de %d)",
                 ruta, len(self.activas()), len(self._creds))

    # ------------------------------------------------------------------ #
    def _cargar(self) -> None:
        if not os.path.exists(self._ruta):
            return
        try:
            with open(self._ruta, encoding="utf-8") as f:
                datos = json.load(f)
            for d in datos:
                c = Credencial(**d)
                self._creds[c.identificador] = c
        except (OSError, ValueError) as exc:
            # No se borra el archivo: puede ser recuperable a mano y perderlo
            # significaria dejar sin acceso a todo el personal.
            log.error("no se pudo leer el registro (%s); se arranca vacio", exc)

    def _guardar(self) -> None:
        """Escritura atomica: temporal + rename. Un corte de energia a mitad
        de la escritura dejaria el registro truncado y sin acceso a nadie."""
        tmp = self._ruta + ".tmp"
        datos = [asdict(c) for c in self._creds.values()]
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._ruta)

    # ------------------------------------------------------------------ #
    # CU-11: alta
    # ------------------------------------------------------------------ #
    def alta(self, nombre: str, rol: str,
             identificador: str | None = None) -> Credencial:
        """Registra a una persona. Devuelve la credencial creada.

        Lanza ValueError si el rol no existe o el identificador ya esta en uso.
        """
        r = Rol.desde_texto(rol)                 # valida antes de tocar nada
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("el nombre no puede estar vacio")

        with self._lock:
            if identificador is None:
                identificador = nuevo_identificador()
                while identificador in self._creds:
                    identificador = nuevo_identificador()
            elif identificador in self._creds:
                raise ValueError(f"el identificador {identificador} ya existe")

            cred = Credencial(
                identificador=identificador,
                nombre=nombre,
                rol=r.value,
                alta=_ahora(),
            )
            self._creds[identificador] = cred
            self._guardar()

        log.info("ALTA %s | %s | %s", identificador, nombre, r.value)
        return cred

    # ------------------------------------------------------------------ #
    # CU-12: baja
    # ------------------------------------------------------------------ #
    def baja(self, identificador: str, nota: str | None = None) -> Credencial:
        """Revoca el acceso. El registro se conserva como historico."""
        with self._lock:
            cred = self._creds.get(identificador)
            if cred is None:
                raise ValueError(f"no existe la credencial {identificador}")
            if not cred.activa:
                raise ValueError(f"la credencial {identificador} ya estaba de baja")
            cred.activa = False
            cred.baja = _ahora()
            cred.notas = nota
            self._guardar()

        log.info("BAJA %s | %s | %s", identificador, cred.nombre, cred.rol)
        return cred

    # ------------------------------------------------------------------ #
    # Vaciado total (BORRAR_CREDENCIALES)
    # ------------------------------------------------------------------ #
    def vaciar(self) -> int:
        """Elimina TODAS las credenciales, activas y revocadas.

        A diferencia de la baja, no deja historico: es para empezar de cero
        (por ejemplo, antes de una demostracion). Devuelve cuantas habia.
        """
        with self._lock:
            n = len(self._creds)
            self._creds.clear()
            self._guardar()
        log.warning("registro de credenciales vaciado: %d eliminadas", n)
        return n

    # ------------------------------------------------------------------ #
    # Consulta: la usa el lector de QR en cada deteccion
    # ------------------------------------------------------------------ #
    def buscar(self, identificador: str) -> Credencial | None:
        """Credencial ACTIVA con ese identificador, o None.

        Devuelve None tanto si no existe como si esta de baja: para el
        control de acceso el efecto es el mismo.
        """
        with self._lock:
            cred = self._creds.get(identificador)
        return cred if cred is not None and cred.activa else None

    def activas(self) -> list[Credencial]:
        with self._lock:
            return [c for c in self._creds.values() if c.activa]

    def todas(self) -> list[Credencial]:
        with self._lock:
            return list(self._creds.values())

    def resumen(self) -> str:
        """Listado para el vigilante (comando LISTAR)."""
        act = self.activas()
        if not act:
            return "no hay credenciales activas"
        lineas = [f"{len(act)} credenciales activas:"]
        for c in sorted(act, key=lambda x: (x.rol, x.nombre)):
            lineas.append(f"  {c.identificador}  {c.rol:<14} {c.nombre}")
        return "\n".join(lineas)
