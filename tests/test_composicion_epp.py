"""Composición del módulo de EPP con los valores decididos (SPEC/9 §5.4; D4 y D5 del 24/10/2026)."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from freezegun import freeze_time

from src.composicion_epp import (
    PARAMETROS_DECIDIDOS,
    DestinoEPP,
    PublicadorEnMemoria,
    RelojSistema,
    crear_evaluador_epp,
)
from src.ppe.application.evaluar_cumplimiento import FotogramaEPP, PersonaEnEscena
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import EventoInfraccion, Incumplimiento, InfraccionIniciada
from src.ppe.domain.reglas import ReglasEPP, ReglaZona
from tests.dobles_ppe import RelojFalso
from tests.escenas_ppe import Operario

CASCO, CHALECO = ElementoEPP.CASCO, ElementoEPP.CHALECO
ANDEN = "Anden"
UN_SEGUNDO = timedelta(seconds=1)
VERSION = "epp-1.0.0"
RETENCION_DECIDIDA_DIAS = 30  # D5
INICIO = datetime(2026, 10, 24, 8, 0, tzinfo=UTC)
ANA = Operario(track_id=1)
CUADRO = np.zeros((400, 200, 3), dtype=np.uint8)
REGLAS = ReglasEPP(
    globales=frozenset(),
    zonas=(ReglaZona(ANDEN, ((0, 0), (10, 0), (0, 10)), frozenset({CASCO})),),
)


@pytest.fixture
def conectar(tmp_path: Path) -> Callable[[], sqlite3.Connection]:
    ruta = tmp_path / "tenant.db"
    return lambda: sqlite3.connect(ruta)


@pytest.fixture
def publicador() -> PublicadorEnMemoria:
    return PublicadorEnMemoria()


@pytest.fixture
def destino(
    conectar: Callable[[], sqlite3.Connection], tmp_path: Path, publicador: PublicadorEnMemoria
) -> DestinoEPP:
    return DestinoEPP(conectar, tmp_path / "snapshots", publicador)


def _sin_casco() -> FotogramaEPP:
    persona = PersonaEnEscena(ANA.track_id, ANA.caja((0, 0, 100, 300)), frozenset({ANDEN}), "Ana")
    return FotogramaEPP((persona,), ANA.anclas, ANA.epp(CHALECO), CUADRO)


def _iniciada(elemento: ElementoEPP) -> InfraccionIniciada:
    return InfraccionIniciada(Incumplimiento(1, "Ana", elemento, ANDEN), INICIO, VERSION, None)


def _infracciones(conectar: Callable[[], sqlite3.Connection]) -> list[tuple[object, ...]]:
    conexion = conectar()
    filas = conexion.execute(
        "SELECT employee_name, zona, elemento, estado_notificacion, modelo_version "
        "FROM ppe_infracciones"
    ).fetchall()
    conexion.close()
    return filas


def test_los_parametros_son_los_que_decidio_el_negocio() -> None:
    assert PARAMETROS_DECIDIDOS.tiempo_confirmacion == timedelta(seconds=4)
    assert PARAMETROS_DECIDIDOS.enfriamiento == timedelta(minutes=10)
    assert PARAMETROS_DECIDIDOS.retencion_dias == RETENCION_DECIDIDA_DIAS


def test_los_parametros_tecnicos_son_los_propuestos_en_el_plan() -> None:
    parametros = PARAMETROS_DECIDIDOS

    tecnicos = (
        parametros.fraccion_ausente_minima,
        parametros.presentes_para_recuperar,
        parametros.tiempo_limpieza,
        parametros.ioa_minimo_ancla,
        parametros.ioa_minimo_epp,
        parametros.cada_n_frames,
    )

    assert tecnicos == (0.8, 5, timedelta(seconds=30), 0.5, 0.5, 1)


@freeze_time("2026-10-24 09:15:30")
def test_el_reloj_del_sistema_da_la_hora_actual_en_utc() -> None:
    assert RelojSistema().ahora() == datetime(2026, 10, 24, 9, 15, 30, tzinfo=UTC)


def test_el_publicador_entrega_cada_evento_a_cada_suscriptor_en_orden() -> None:
    publicador = PublicadorEnMemoria()
    recibidos: list[tuple[str, object]] = []
    publicador.suscribir(lambda evento: recibidos.append(("uno", evento)))
    publicador.suscribir(lambda evento: recibidos.append(("dos", evento)))
    eventos = [_iniciada(CASCO), _iniciada(CHALECO)]

    publicador.publicar(eventos[0])
    publicador.publicar(eventos[1])

    assert recibidos == [
        ("uno", eventos[0]),
        ("dos", eventos[0]),
        ("uno", eventos[1]),
        ("dos", eventos[1]),
    ]


def test_sin_casco_4_segundos_en_una_zona_que_lo_exige_queda_una_infraccion_pendiente(
    destino: DestinoEPP, conectar: Callable[[], sqlite3.Connection], tmp_path: Path
) -> None:
    reloj = RelojFalso(INICIO)
    evaluador = crear_evaluador_epp(destino, REGLAS, VERSION, reloj)

    evaluador.evaluar(_sin_casco())
    reloj.avanzar(3 * UN_SEGUNDO)
    evaluador.evaluar(_sin_casco())
    antes_de_4_s = _infracciones(conectar)
    reloj.avanzar(UN_SEGUNDO)
    evaluador.evaluar(_sin_casco())

    assert antes_de_4_s == []
    assert _infracciones(conectar) == [("Ana", ANDEN, "casco", "PENDIENTE", VERSION)]
    assert len(list((tmp_path / "snapshots" / "epp").rglob("*_casco.jpg"))) == 1


def test_la_infraccion_se_publica_a_la_interfaz(
    destino: DestinoEPP, publicador: PublicadorEnMemoria
) -> None:
    reloj = RelojFalso(INICIO)
    evaluador = crear_evaluador_epp(destino, REGLAS, VERSION, reloj)
    publicados: list[EventoInfraccion] = []
    publicador.suscribir(publicados.append)

    evaluador.evaluar(_sin_casco())
    reloj.avanzar(4 * UN_SEGUNDO)
    evaluador.evaluar(_sin_casco())

    assert [(e.incumplimiento.elemento, e.inicio) for e in publicados] == [
        (CASCO, INICIO + 4 * UN_SEGUNDO)
    ]


def test_crear_el_evaluador_dos_veces_sobre_la_misma_base_no_falla(destino: DestinoEPP) -> None:
    crear_evaluador_epp(destino, REGLAS, VERSION, RelojFalso(INICIO))

    evaluador = crear_evaluador_epp(destino, REGLAS, VERSION, RelojFalso(INICIO))

    assert evaluador.reglas == REGLAS
