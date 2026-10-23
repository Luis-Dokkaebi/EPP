"""Lectura de infracciones y turnos para el reporte de cumplimiento (SPEC/9 §8.4; §9)."""

import functools
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.analysis.cumplimiento_epp import InfraccionRegistrada
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import Incumplimiento, InfraccionFinalizada, InfraccionIniciada
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from src.storage.reporte_cumplimiento import leer_infracciones, leer_turnos

Conectar = functools.partial[sqlite3.Connection]
INICIO = datetime(2026, 10, 22, 8, 0, tzinfo=UTC)
DIA = timedelta(days=1)
INYECCION = "x'); DROP TABLE ppe_infracciones; --"


@pytest.fixture
def conectar(tmp_path: Path) -> Conectar:
    conectar = functools.partial(sqlite3.connect, tmp_path / "tracking.db")
    crear_tabla_infracciones(conectar)
    return conectar


def _registrar(
    conectar: Conectar, nombre: str | None, inicio: datetime, minutos: int | None
) -> None:
    incumplimiento = Incumplimiento(1, nombre, ElementoEPP.CASCO, "Boca de pozo")
    repositorio = RepositorioInfraccionesSQLite(conectar)
    repositorio.guardar(InfraccionIniciada(incumplimiento, inicio, "epp-0.1.0", None))
    if minutos is not None:
        fin = inicio + timedelta(minutes=minutos)
        repositorio.guardar(InfraccionFinalizada(incumplimiento, inicio, "epp-0.1.0", fin))


def _crear_empleados(conectar: Conectar, *empleados: tuple[str, str | None]) -> None:
    with closing(conectar()) as conexion, conexion:
        conexion.execute("CREATE TABLE employees (employee_name TEXT PRIMARY KEY, shift TEXT)")
        conexion.executemany("INSERT INTO employees VALUES (?, ?)", empleados)


def test_leer_infracciones_del_periodo_con_su_fin(conectar: Conectar) -> None:
    _registrar(conectar, "Ana", INICIO, minutos=10)
    _registrar(conectar, None, INICIO + timedelta(hours=1), minutos=None)

    infracciones = leer_infracciones(conectar, INICIO, INICIO + DIA)

    assert infracciones == [
        InfraccionRegistrada(
            "Ana", "Boca de pozo", "casco", INICIO, INICIO + timedelta(minutes=10)
        ),
        InfraccionRegistrada(None, "Boca de pozo", "casco", INICIO + timedelta(hours=1), None),
    ]


def test_leer_infracciones_incluye_el_desde_y_excluye_el_hasta(conectar: Conectar) -> None:
    _registrar(conectar, "Antes", INICIO - timedelta(microseconds=1), minutos=1)
    _registrar(conectar, "Justo", INICIO, minutos=1)
    _registrar(conectar, "Ultima", INICIO + DIA - timedelta(microseconds=1), minutos=1)
    _registrar(conectar, "Fuera", INICIO + DIA, minutos=1)

    infracciones = leer_infracciones(conectar, INICIO, INICIO + DIA)

    assert [infraccion.persona for infraccion in infracciones] == ["Justo", "Ultima"]


def test_leer_infracciones_compara_instantes_aunque_cambie_el_huso(conectar: Conectar) -> None:
    _registrar(conectar, "Ana", INICIO, minutos=1)
    argentina = timezone(timedelta(hours=-3))

    infracciones = leer_infracciones(
        conectar, INICIO.astimezone(argentina), (INICIO + DIA).astimezone(argentina)
    )

    assert [infraccion.persona for infraccion in infracciones] == ["Ana"]


def test_leer_turnos_de_los_empleados_con_turno(conectar: Conectar) -> None:
    _crear_empleados(conectar, ("Ana", "Matutino"), ("Luis", ""), ("Eva", None))

    assert leer_turnos(conectar) == {"Ana": "Matutino"}


def test_leer_turnos_sin_tabla_de_empleados_no_tiene_turnos(conectar: Conectar) -> None:
    assert leer_turnos(conectar) == {}


def test_la_lectura_trata_la_inyeccion_sql_como_texto(conectar: Conectar) -> None:
    _registrar(conectar, INYECCION, INICIO, minutos=1)
    _crear_empleados(conectar, (INYECCION, INYECCION))

    (infraccion,) = leer_infracciones(conectar, INICIO, INICIO + DIA)

    assert infraccion.persona == INYECCION
    assert leer_turnos(conectar) == {INYECCION: INYECCION}
