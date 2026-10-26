"""Composición del módulo de EPP con los valores decididos (SPEC/9 §5.4; D4 y D5 del 24/10/2026)."""

import dataclasses
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from freezegun import freeze_time

from config import config
from src.composicion_epp import (
    PARAMETROS_DECIDIDOS,
    DestinoEPP,
    PublicadorEnMemoria,
    RelojSistema,
    crear_evaluador_epp,
    crear_integracion_epp_de_la_app,
    modelo_detecta_epp,
    modulo_habilitado,
)
from src.inference.types import ClaseObjeto
from src.ppe.application.evaluar_cumplimiento import FotogramaEPP, PersonaEnEscena
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import EventoInfraccion, Incumplimiento, InfraccionIniciada
from src.ppe.domain.reglas import ReglasEPP, ReglaZona
from src.zones.formato_zonas import escribir_zonas
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


def test_los_parametros_no_se_pueden_cambiar_en_caliente() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        PARAMETROS_DECIDIDOS.enfriamiento = timedelta(0)  # type: ignore[misc]  # se verifica que no se pueda asignar


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


# --- Cuándo se activa el módulo (D3, D10) ------------------------------------------------------


@pytest.mark.parametrize(
    ("clases", "detecta"),
    [
        ({ClaseObjeto.PERSONA, ClaseObjeto.CASCO, ClaseObjeto.CHALECO, ClaseObjeto.CABEZA}, True),
        ({ClaseObjeto.PERSONA, ClaseObjeto.CELULAR}, False),
        ({ClaseObjeto.PERSONA, ClaseObjeto.CHALECO, ClaseObjeto.CABEZA}, False),
        ({ClaseObjeto.PERSONA, ClaseObjeto.CASCO, ClaseObjeto.CABEZA}, False),
        ({ClaseObjeto.PERSONA, ClaseObjeto.CASCO, ClaseObjeto.CHALECO}, False),
        ({ClaseObjeto.CASCO, ClaseObjeto.CHALECO, ClaseObjeto.CABEZA}, True),
    ],
    ids=["modelo_epp", "modelo_coco", "sin_casco", "sin_chaleco", "sin_cabeza", "lo_justo"],
)
def test_el_modelo_detecta_epp_solo_si_ve_casco_chaleco_y_cabeza(
    clases: set[ClaseObjeto], detecta: bool
) -> None:
    assert modelo_detecta_epp(frozenset(clases)) is detecta


class LicenciaFalsa:
    def __init__(self, *modulos: str) -> None:
        self._modulos = modulos

    def incluye_modulo(self, modulo: str) -> bool:
        return modulo in self._modulos


@pytest.mark.parametrize(
    ("licencia", "habilitado"),
    [(None, False), (LicenciaFalsa("reportes"), False), (LicenciaFalsa("reportes", "epp"), True)],
    ids=["sin_licencia", "licencia_sin_epp", "licencia_con_epp"],
)
def test_el_modulo_se_habilita_solo_con_una_licencia_que_incluye_epp(
    licencia: LicenciaFalsa | None, habilitado: bool
) -> None:
    assert modulo_habilitado(licencia) is habilitado


CLASES_EPP = {"0": "persona", "1": "casco", "2": "chaleco", "3": "cabeza"}
CLASES_COCO = {"0": "persona", "67": "celular"}


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, str]], Path]:
    """Configura la app sobre tmp_path con un modelo que detecta las clases pedidas."""

    def configurar(clases: dict[str, str]) -> Path:
        manifiesto = {"modelos": [{"archivo": "epp.onnx", "version": VERSION, "clases": clases}]}
        (tmp_path / "manifest.json").write_text(json.dumps(manifiesto), encoding="utf-8")
        escribir_zonas(tmp_path / "zonas.json", REGLAS.zonas)
        monkeypatch.setattr(config, "MODEL_PATH", str(tmp_path / "epp.onnx"))
        monkeypatch.setattr(config, "MANIFEST_PATH", str(tmp_path / "manifest.json"))
        monkeypatch.setattr(config, "get_zonas_file", lambda: str(tmp_path / "zonas.json"))
        monkeypatch.setattr(config, "get_db_path", lambda: str(tmp_path / "tenant.db"))
        monkeypatch.setattr(config, "get_snapshots_dir", lambda: str(tmp_path / "snapshots"))
        return tmp_path

    return configurar


@pytest.mark.parametrize(
    ("clases", "licencia"),
    [(CLASES_EPP, LicenciaFalsa("reportes")), (CLASES_COCO, LicenciaFalsa("epp"))],
    ids=["licencia_sin_epp", "modelo_sin_epp"],
)
def test_sin_licencia_o_sin_modelo_de_epp_el_modulo_no_se_activa(
    app: Callable[[dict[str, str]], Path], clases: dict[str, str], licencia: LicenciaFalsa
) -> None:
    app(clases)

    assert crear_integracion_epp_de_la_app(PublicadorEnMemoria(), licencia) is None


def test_con_licencia_y_modelo_de_epp_evalua_con_las_zonas_del_tenant(
    app: Callable[[dict[str, str]], Path],
) -> None:
    carpeta = app(CLASES_EPP)
    integracion = crear_integracion_epp_de_la_app(PublicadorEnMemoria(), LicenciaFalsa("epp"))
    persona = _sin_casco().personas[0]

    assert integracion is not None

    estados = integracion.evaluar(CUADRO, [persona], [])

    assert estados[persona.track_id].exigidos == frozenset({CASCO})
    assert (carpeta / "tenant.db").is_file()
