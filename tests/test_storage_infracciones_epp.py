"""Persistencia de infracciones de EPP en SQLite (SPEC/9 §6.1, C-05; CLAUDE.md §9)."""

import functools
import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import (
    EventoInfraccion,
    Incumplimiento,
    InfraccionFinalizada,
    InfraccionIniciada,
)
from src.storage.database_manager import DatabaseManager
from src.storage.infracciones_epp import (
    InfraccionNoEncontradaError,
    RepositorioInfraccionesSQLite,
    crear_tabla_infracciones,
    eliminar_tabla_infracciones,
)
from tests.dobles_ppe import INICIO

VERSION = "epp-0.1.0"
COLUMNAS = [
    "id",
    "track_id",
    "employee_name",
    "zona",
    "elemento",
    "inicio",
    "fin",
    "duracion_s",
    "evidencia_path",
    "estado_notificacion",
    "intentos_notificacion",
    "modelo_version",
    "reconocida_por",
    "reconocida_en",
]
ANA_SIN_CASCO = Incumplimiento(1, "Ana", ElementoEPP.CASCO, "Boca de pozo")
NOVENTA_SEGUNDOS = timedelta(seconds=90)
INYECCION = "x'); DROP TABLE ppe_infracciones; --"


@pytest.fixture
def conectar(tmp_path: Path) -> functools.partial[sqlite3.Connection]:
    conectar = functools.partial(sqlite3.connect, tmp_path / "tracking.db")
    crear_tabla_infracciones(conectar)
    return conectar


@pytest.fixture
def repositorio(conectar: functools.partial[sqlite3.Connection]) -> RepositorioInfraccionesSQLite:
    return RepositorioInfraccionesSQLite(conectar)


def _iniciada(incumplimiento: Incumplimiento = ANA_SIN_CASCO) -> InfraccionIniciada:
    return InfraccionIniciada(incumplimiento, INICIO, VERSION, evidencia="ev/1.jpg")


def _finalizada(incumplimiento: Incumplimiento = ANA_SIN_CASCO) -> InfraccionFinalizada:
    return InfraccionFinalizada(incumplimiento, INICIO, VERSION, fin=INICIO + NOVENTA_SEGUNDOS)


def _consultar(
    conectar: functools.partial[sqlite3.Connection], sql: str
) -> list[tuple[object, ...]]:
    with closing(conectar()) as conexion:
        return conexion.execute(sql).fetchall()


def _filas(conectar: functools.partial[sqlite3.Connection]) -> list[tuple[object, ...]]:
    return _consultar(conectar, "SELECT * FROM ppe_infracciones ORDER BY id")


def test_crear_tabla_infracciones_tiene_las_columnas_del_plan(
    conectar: functools.partial[sqlite3.Connection],
) -> None:
    columnas = [fila[1] for fila in _consultar(conectar, "PRAGMA table_info(ppe_infracciones)")]

    assert columnas == COLUMNAS


def test_crear_tabla_infracciones_sobre_una_base_heredada_conserva_sus_datos(
    tmp_path: Path,
) -> None:
    ruta = tmp_path / "heredada.db"
    DatabaseManager(db_path=str(ruta)).insert_record(7, 1.0, 2.0, "Z", 1, employee_name="Ana")
    conectar = functools.partial(sqlite3.connect, ruta)

    crear_tabla_infracciones(conectar)
    crear_tabla_infracciones(conectar)

    tablas = _consultar(conectar, "SELECT name FROM sqlite_master WHERE type = 'table'")
    seguimiento = _consultar(conectar, "SELECT track_id, employee_name FROM tracking")
    assert (("ppe_infracciones",) in tablas, seguimiento) == (True, [(7, "Ana")])


def test_eliminar_tabla_infracciones_revierte_sin_tocar_las_demas(tmp_path: Path) -> None:
    ruta = tmp_path / "heredada.db"
    DatabaseManager(db_path=str(ruta)).insert_record(7, 1.0, 2.0, "Z", 1)
    conectar = functools.partial(sqlite3.connect, ruta)
    crear_tabla_infracciones(conectar)

    eliminar_tabla_infracciones(conectar)
    eliminar_tabla_infracciones(conectar)

    tablas = {fila[0] for fila in _consultar(conectar, "SELECT name FROM sqlite_master")}
    assert ("ppe_infracciones" in tablas, "tracking" in tablas) == (False, True)


def test_guardar_infraccion_iniciada_inserta_una_fila_pendiente(
    repositorio: RepositorioInfraccionesSQLite, conectar: functools.partial[sqlite3.Connection]
) -> None:
    repositorio.guardar(_iniciada())

    inicio = INICIO.isoformat()
    esperada = (1, 1, "Ana", "Boca de pozo", "casco", inicio, None, None, "ev/1.jpg", "PENDIENTE")
    assert _filas(conectar) == [(*esperada, 0, VERSION, None, None)]


def test_guardar_infraccion_de_la_regla_global_usa_su_zona_propia(
    repositorio: RepositorioInfraccionesSQLite, conectar: functools.partial[sqlite3.Connection]
) -> None:
    sin_zona = Incumplimiento(3, None, ElementoEPP.CHALECO, None)

    repositorio.guardar(_iniciada(sin_zona))

    filas = _consultar(conectar, "SELECT employee_name, zona, elemento FROM ppe_infracciones")
    assert filas == [(None, "(toda la escena)", "chaleco")]


def test_guardar_infraccion_finalizada_cierra_solo_la_fila_abierta(
    repositorio: RepositorioInfraccionesSQLite, conectar: functools.partial[sqlite3.Connection]
) -> None:
    otra = Incumplimiento(2, None, ElementoEPP.CASCO, "Boca de pozo")
    repositorio.guardar(_iniciada())
    repositorio.guardar(_iniciada(otra))

    repositorio.guardar(_finalizada())

    cierres = _consultar(conectar, "SELECT track_id, fin, duracion_s FROM ppe_infracciones")
    fin = (INICIO + NOVENTA_SEGUNDOS).isoformat()
    assert cierres == [(1, fin, NOVENTA_SEGUNDOS.total_seconds()), (2, None, None)]


def test_guardar_infraccion_finalizada_sin_fila_abierta_falla(
    repositorio: RepositorioInfraccionesSQLite,
) -> None:
    repositorio.guardar(_iniciada())
    repositorio.guardar(_finalizada())

    with pytest.raises(
        InfraccionNoEncontradaError,
        match=r"^No hay infracción abierta para el track 1, casco desde "
        r"2026-10-22T08:00:00\+00:00$",
    ):
        repositorio.guardar(_finalizada())


def test_guardar_un_evento_desconocido_falla(repositorio: RepositorioInfraccionesSQLite) -> None:
    with pytest.raises(TypeError, match=r"^Evento de infracción desconocido: EventoInfraccion$"):
        repositorio.guardar(EventoInfraccion(ANA_SIN_CASCO, INICIO, VERSION))


def test_guardar_valores_con_inyeccion_sql_los_trata_como_texto(
    repositorio: RepositorioInfraccionesSQLite, conectar: functools.partial[sqlite3.Connection]
) -> None:
    malicioso = Incumplimiento(9, INYECCION, ElementoEPP.CASCO, "Z' OR '1'='1")
    repositorio.guardar(_iniciada())
    repositorio.guardar(_iniciada(malicioso))

    with pytest.raises(InfraccionNoEncontradaError):
        repositorio.guardar(_finalizada(Incumplimiento(1, "Ana", ElementoEPP.CASCO, "' OR '1'='1")))

    filas = _consultar(conectar, "SELECT employee_name, zona, fin FROM ppe_infracciones")
    assert filas == [("Ana", "Boca de pozo", None), (INYECCION, "Z' OR '1'='1", None)]
