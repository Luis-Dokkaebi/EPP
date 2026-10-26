"""Lectura de infracciones y turnos para el reporte de cumplimiento de EPP (SPEC/9 §8.4).

El período se filtra comparando instantes ya interpretados, no textos: así no depende del huso
horario con el que se haya guardado cada hora. Toda consulta es parametrizada o fija (§9).
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime, timedelta, tzinfo

from src.analysis.cumplimiento_epp import InfraccionRegistrada, Presencia

_INFRACCIONES = (
    "SELECT employee_name, zona, elemento, inicio, fin FROM ppe_infracciones ORDER BY id"
)
_HAY_TABLA = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?"
# El seguimiento guarda la hora local sin huso (datetime.now().isoformat()). El filtro por texto
# es solo un primer recorte con un día de margen; el período exacto se filtra en Python.
_PRESENCIAS = (
    "SELECT employee_name, zone, timestamp, inside_zone FROM tracking "
    "WHERE employee_name IS NOT NULL AND employee_name NOT IN ('', ?) "
    "AND timestamp >= ? AND timestamp < ?"
)
NOMBRE_DESCONOCIDO = "Unknown"
MARGEN = timedelta(days=1)
_TURNOS = "SELECT employee_name, shift FROM employees WHERE shift IS NOT NULL AND shift != ''"


def leer_infracciones(
    conectar: Callable[[], sqlite3.Connection], desde: datetime, hasta: datetime
) -> list[InfraccionRegistrada]:
    """Infracciones que empezaron en [desde, hasta), en orden de registro."""
    with closing(conectar()) as conexion:
        filas = conexion.execute(_INFRACCIONES).fetchall()
    infracciones = [
        InfraccionRegistrada(
            persona,
            zona,
            elemento,
            datetime.fromisoformat(inicio),
            None if fin is None else datetime.fromisoformat(fin),
        )
        for persona, zona, elemento, inicio, fin in filas
    ]
    return [infraccion for infraccion in infracciones if desde <= infraccion.inicio < hasta]


def leer_turnos(conectar: Callable[[], sqlite3.Connection]) -> dict[str, str]:
    """Turno de cada empleado que lo tiene cargado; sin tabla de empleados, ninguno."""
    with closing(conectar()) as conexion:
        if conexion.execute(_HAY_TABLA, ("employees",)).fetchone() is None:
            return {}
        return dict(conexion.execute(_TURNOS).fetchall())


def leer_presencias(
    conectar: Callable[[], sqlite3.Connection],
    desde: datetime,
    hasta: datetime,
    zona_horaria: tzinfo,
) -> list[Presencia]:
    """Presencias de personas reconocidas en [desde, hasta); sin tabla tracking, ninguna.

    Una hora guardada sin huso se interpreta en el huso horario de la sucursal.
    """
    limites = (
        NOMBRE_DESCONOCIDO,
        _local(desde - MARGEN, zona_horaria),
        _local(hasta + MARGEN, zona_horaria),
    )
    with closing(conectar()) as conexion:
        if conexion.execute(_HAY_TABLA, ("tracking",)).fetchone() is None:
            return []
        filas = conexion.execute(_PRESENCIAS, limites).fetchall()
    presencias = [
        Presencia(persona, zona, _instante(hora, zona_horaria), bool(dentro))
        for persona, zona, hora, dentro in filas
    ]
    return [presencia for presencia in presencias if desde <= presencia.instante < hasta]


def _local(instante: datetime, zona_horaria: tzinfo) -> str:
    return instante.astimezone(zona_horaria).replace(tzinfo=None).isoformat()


def _instante(hora: str, zona_horaria: tzinfo) -> datetime:
    instante = datetime.fromisoformat(hora)
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=zona_horaria)
