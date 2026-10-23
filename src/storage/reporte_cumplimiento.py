"""Lectura de infracciones y turnos para el reporte de cumplimiento de EPP (SPEC/9 §8.4).

El período se filtra comparando instantes ya interpretados, no textos: así no depende del huso
horario con el que se haya guardado cada hora. Toda consulta es parametrizada o fija (§9).
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime

from src.analysis.cumplimiento_epp import InfraccionRegistrada

_INFRACCIONES = (
    "SELECT employee_name, zona, elemento, inicio, fin FROM ppe_infracciones ORDER BY id"
)
_HAY_EMPLEADOS = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?"
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
        if conexion.execute(_HAY_EMPLEADOS, ("employees",)).fetchone() is None:
            return {}
        return dict(conexion.execute(_TURNOS).fetchall())
