"""Persistencia de las infracciones de EPP en SQLite (SPEC/9 §6.1, C-05).

Migración aditiva (skill migration): `crear_tabla_infracciones` agrega la tabla sin tocar las
existentes y es idempotente. La reversión, `eliminar_tabla_infracciones`, borra solo esa tabla y
sus datos: es destructiva y se ejecuta a mano. La tabla vive en la misma base que el resto, así que
hereda su cifrado en reposo (src/security/db_crypto.py). Toda consulta es parametrizada (§9).
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing

from src.ppe.domain.infracciones import (
    EventoInfraccion,
    InfraccionFinalizada,
    InfraccionIniciada,
)

# La columna zona es NOT NULL; la regla global (zona None en el dominio) se guarda con este nombre.
ZONA_DE_LA_REGLA_GLOBAL = "(toda la escena)"

_CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS ppe_infracciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    employee_name TEXT,
    zona TEXT NOT NULL,
    elemento TEXT NOT NULL,
    inicio TEXT NOT NULL,
    fin TEXT,
    duracion_s REAL,
    evidencia_path TEXT,
    estado_notificacion TEXT NOT NULL DEFAULT 'PENDIENTE',
    intentos_notificacion INTEGER NOT NULL DEFAULT 0,
    modelo_version TEXT NOT NULL,
    reconocida_por TEXT,
    reconocida_en TEXT
)
"""
_ELIMINAR_TABLA = "DROP TABLE IF EXISTS ppe_infracciones"
_INSERTAR = (
    "INSERT INTO ppe_infracciones (track_id, employee_name, zona, elemento, inicio, "
    "evidencia_path, modelo_version) VALUES (?, ?, ?, ?, ?, ?, ?)"
)
_CERRAR = (
    "UPDATE ppe_infracciones SET fin = ?, duracion_s = ? "
    "WHERE track_id = ? AND zona = ? AND elemento = ? AND inicio = ? AND fin IS NULL"
)


class InfraccionNoEncontradaError(LookupError):
    """Se quiso cerrar una infracción que no está abierta en la base."""


def crear_tabla_infracciones(conectar: Callable[[], sqlite3.Connection]) -> None:
    """Crea la tabla si no existe (paso "expandir"; idempotente)."""
    _ejecutar(conectar, _CREAR_TABLA, ())


def eliminar_tabla_infracciones(conectar: Callable[[], sqlite3.Connection]) -> None:
    """Revierte la migración: borra la tabla y sus registros (destructivo, manual)."""
    _ejecutar(conectar, _ELIMINAR_TABLA, ())


class RepositorioInfraccionesSQLite:
    """Implementa RepositorioInfraccionesPort sobre la base SQLite del tenant."""

    def __init__(self, conectar: Callable[[], sqlite3.Connection]) -> None:
        self._conectar = conectar

    def guardar(self, evento: EventoInfraccion) -> None:
        if isinstance(evento, InfraccionIniciada):
            self._insertar(evento)
        elif isinstance(evento, InfraccionFinalizada):
            self._cerrar(evento)
        else:
            raise TypeError(f"Evento de infracción desconocido: {type(evento).__name__}")

    def _insertar(self, iniciada: InfraccionIniciada) -> None:
        incumplimiento = iniciada.incumplimiento
        parametros = (
            incumplimiento.track_id,
            incumplimiento.nombre,
            _zona(incumplimiento.zona),
            incumplimiento.elemento.value,
            iniciada.inicio.isoformat(),
            iniciada.evidencia,
            iniciada.version_modelo,
        )
        _ejecutar(self._conectar, _INSERTAR, parametros)

    def _cerrar(self, finalizada: InfraccionFinalizada) -> None:
        incumplimiento = finalizada.incumplimiento
        parametros = (
            finalizada.fin.isoformat(),
            finalizada.duracion.total_seconds(),
            incumplimiento.track_id,
            _zona(incumplimiento.zona),
            incumplimiento.elemento.value,
            finalizada.inicio.isoformat(),
        )
        if _ejecutar(self._conectar, _CERRAR, parametros) != 1:
            raise InfraccionNoEncontradaError(
                f"No hay infracción abierta para el track {incumplimiento.track_id}, "
                f"{incumplimiento.elemento.value} desde {finalizada.inicio.isoformat()}"
            )


def _zona(zona: str | None) -> str:
    return ZONA_DE_LA_REGLA_GLOBAL if zona is None else zona


def _ejecutar(
    conectar: Callable[[], sqlite3.Connection], sql: str, parametros: tuple[object, ...]
) -> int:
    """Ejecuta una sentencia en su propia transacción y devuelve las filas afectadas."""
    with closing(conectar()) as conexion, conexion:
        return conexion.execute(sql, parametros).rowcount
