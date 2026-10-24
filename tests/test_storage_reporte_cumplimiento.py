"""Lectura de infracciones y turnos para el reporte de cumplimiento (SPEC/9 §8.4; §9)."""

import functools
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.analysis.cumplimiento_epp import InfraccionRegistrada, Presencia
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import Incumplimiento, InfraccionFinalizada, InfraccionIniciada
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from src.storage.reporte_cumplimiento import leer_infracciones, leer_presencias, leer_turnos

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


# --- Presencias por zona desde la tabla tracking (§5.4) ---

ARGENTINA = timezone(timedelta(hours=-3))
DESDE = datetime(2026, 10, 22, 0, 0, tzinfo=ARGENTINA)
HASTA = DESDE + DIA


def _tracking(conectar: Conectar, *filas: tuple[str | None, str, str, int]) -> None:
    with closing(conectar()) as conexion, conexion:
        conexion.execute(
            "CREATE TABLE IF NOT EXISTS tracking (employee_name TEXT, timestamp TEXT, zone TEXT, "
            "inside_zone INTEGER)"
        )
        conexion.executemany("INSERT INTO tracking VALUES (?, ?, ?, ?)", filas)


def test_las_presencias_salen_de_tracking_con_la_hora_en_el_huso_de_la_sucursal(
    conectar: Conectar,
) -> None:
    _tracking(conectar, ("Ana", "2026-10-22T08:00:00.500000", "Anden", 1))

    presencias = leer_presencias(conectar, DESDE, HASTA, ARGENTINA)

    instante = datetime(2026, 10, 22, 8, 0, 0, 500000, tzinfo=ARGENTINA)
    assert presencias == [Presencia("Ana", "Anden", instante, True)]


def test_las_presencias_ignoran_a_quien_no_fue_reconocido(conectar: Conectar) -> None:
    hora = "2026-10-22T08:00:00"
    _tracking(conectar, (None, hora, "Anden", 1), ("", hora, "Anden", 1),
              ("Unknown", hora, "Anden", 1), ("Luis", hora, "Anden", 0))  # fmt: skip

    presencias = leer_presencias(conectar, DESDE, HASTA, ARGENTINA)

    assert [(p.persona, p.dentro) for p in presencias] == [("Luis", False)]


@pytest.mark.parametrize(
    "hora", ["2026-10-21T23:59:59", "2026-10-23T00:00:00"], ids=["antes", "despues"]
)
def test_las_presencias_fuera_del_periodo_no_se_leen(conectar: Conectar, hora: str) -> None:
    _tracking(conectar, ("Ana", hora, "Anden", 1))

    assert leer_presencias(conectar, DESDE, HASTA, ARGENTINA) == []


def test_una_presencia_justo_al_inicio_del_periodo_se_lee(conectar: Conectar) -> None:
    _tracking(conectar, ("Ana", "2026-10-22T00:00:00", "Anden", 1))

    (presencia,) = leer_presencias(conectar, DESDE, HASTA, ARGENTINA)

    assert presencia.instante == DESDE


def test_una_hora_guardada_con_huso_se_respeta(conectar: Conectar) -> None:
    _tracking(conectar, ("Ana", "2026-10-22T11:00:00+00:00", "Anden", 1))

    (presencia,) = leer_presencias(conectar, DESDE, HASTA, ARGENTINA)

    assert presencia.instante == datetime(2026, 10, 22, 8, 0, tzinfo=ARGENTINA)


def test_sin_tabla_tracking_no_hay_presencias(conectar: Conectar) -> None:
    assert leer_presencias(conectar, DESDE, HASTA, ARGENTINA) == []
