"""Purga de evidencias de EPP por retención (SPEC/9 §6.2, C-08; AC-019, D5 pendiente)."""

import functools
import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.errores import ConfiguracionInvalidaError
from src.ppe.domain.infracciones import Incumplimiento, InfraccionIniciada
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from src.storage.retencion_evidencias import (
    EvidenciaFueraDeLaCarpetaError,
    RetencionNoConfiguradaError,
    purgar_evidencias_vencidas,
    retencion_de_evidencias,
)
from tests.dobles_ppe import INICIO, RelojFalso

TREINTA_DIAS = timedelta(days=30)
ANA_SIN_CASCO = Incumplimiento(1, "Ana", ElementoEPP.CASCO, "Boca de pozo")


@pytest.fixture
def conectar(tmp_path: Path) -> functools.partial[sqlite3.Connection]:
    conectar = functools.partial(sqlite3.connect, tmp_path / "tracking.db")
    crear_tabla_infracciones(conectar)
    return conectar


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    return tmp_path / "snapshots"


def _registrar(
    conectar: functools.partial[sqlite3.Connection], carpeta: Path, antiguedad: timedelta
) -> Path:
    imagen = carpeta / "epp" / f"{antiguedad.days}.jpg"
    imagen.parent.mkdir(parents=True, exist_ok=True)
    imagen.write_bytes(b"jpg")
    iniciada = InfraccionIniciada(ANA_SIN_CASCO, INICIO - antiguedad, "v", str(imagen))
    RepositorioInfraccionesSQLite(conectar).guardar(iniciada)
    return imagen


def _personales(conectar: functools.partial[sqlite3.Connection]) -> list[tuple[object, ...]]:
    with closing(conectar()) as conexion:
        consulta = "SELECT employee_name, evidencia_path FROM ppe_infracciones ORDER BY id"
        return conexion.execute(consulta).fetchall()


def test_retencion_sin_configurar_falla_porque_la_decide_el_negocio() -> None:
    with pytest.raises(
        RetencionNoConfiguradaError,
        match=r"^Falta la retención de evidencias en días: la define el negocio \(D5\) y no "
        r"tiene valor por omisión$",
    ):
        retencion_de_evidencias(None)


def test_retencion_configurada_en_dias() -> None:
    assert retencion_de_evidencias(30) == TREINTA_DIAS


def test_retencion_menor_que_un_dia_es_invalida() -> None:
    with pytest.raises(ConfiguracionInvalidaError, match=r"^retencion_dias debe ser al menos 1"):
        retencion_de_evidencias(0)


def test_purgar_borra_la_imagen_y_anonimiza_solo_lo_vencido(
    conectar: functools.partial[sqlite3.Connection], carpeta: Path
) -> None:
    vieja = _registrar(conectar, carpeta, timedelta(days=40))
    reciente = _registrar(conectar, carpeta, timedelta(days=1))

    purgadas = purgar_evidencias_vencidas(conectar, carpeta, RelojFalso(), TREINTA_DIAS)

    assert (purgadas, vieja.exists(), reciente.exists()) == (1, False, True)
    assert _personales(conectar) == [(None, None), ("Ana", str(reciente))]


def test_purgar_conserva_lo_que_vence_justo_ahora(
    conectar: functools.partial[sqlite3.Connection], carpeta: Path
) -> None:
    justo = _registrar(conectar, carpeta, TREINTA_DIAS)

    purgadas = purgar_evidencias_vencidas(conectar, carpeta, RelojFalso(), TREINTA_DIAS)

    assert (purgadas, justo.exists()) == (0, True)


def test_purgar_dos_veces_no_vuelve_a_contar_lo_ya_purgado(
    conectar: functools.partial[sqlite3.Connection], carpeta: Path
) -> None:
    vieja = _registrar(conectar, carpeta, timedelta(days=40))
    vieja.unlink()
    purgar_evidencias_vencidas(conectar, carpeta, RelojFalso(), TREINTA_DIAS)

    segunda = purgar_evidencias_vencidas(conectar, carpeta, RelojFalso(), TREINTA_DIAS)

    assert (segunda, _personales(conectar)) == (0, [(None, None)])


def test_purgar_anonimiza_aunque_no_haya_imagen(
    conectar: functools.partial[sqlite3.Connection], carpeta: Path
) -> None:
    sin_imagen = InfraccionIniciada(ANA_SIN_CASCO, INICIO - timedelta(days=40), "v", None)
    RepositorioInfraccionesSQLite(conectar).guardar(sin_imagen)

    purgadas = purgar_evidencias_vencidas(conectar, carpeta, RelojFalso(), TREINTA_DIAS)

    assert (purgadas, _personales(conectar)) == (1, [(None, None)])


def test_purgar_no_borra_archivos_fuera_de_la_carpeta_de_evidencias(
    conectar: functools.partial[sqlite3.Connection], carpeta: Path, tmp_path: Path
) -> None:
    ajena = tmp_path / "ajena.jpg"
    ajena.write_bytes(b"no tocar")
    afuera = InfraccionIniciada(ANA_SIN_CASCO, INICIO - timedelta(days=40), "v", str(ajena))
    RepositorioInfraccionesSQLite(conectar).guardar(afuera)

    with pytest.raises(EvidenciaFueraDeLaCarpetaError, match=r"^La evidencia .+ajena\.jpg no está"):
        purgar_evidencias_vencidas(conectar, carpeta, RelojFalso(), TREINTA_DIAS)

    assert (ajena.exists(), _personales(conectar)) == (True, [("Ana", str(ajena))])
