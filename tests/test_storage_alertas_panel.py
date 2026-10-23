"""Consultas del panel "Alertas EPP" y acuse de recibo (SPEC/9 §8.2; CLAUDE.md §9)."""

import functools
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.alerts.domain.aviso import EstadoNotificacion
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import Incumplimiento, InfraccionIniciada
from src.storage.alertas_panel import (
    AlertaNoReconocibleError,
    AlertaRegistrada,
    RepositorioAlertasSQLite,
)
from src.storage.bandeja_avisos import BandejaAvisosSQLite, agregar_columna_proximo_intento
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from tests.dobles_ppe import INICIO

Conectar = functools.partial[sqlite3.Connection]
INYECCION = "x'); DROP TABLE ppe_infracciones; --"
RECIBIDA = datetime(2026, 10, 22, 8, 30, tzinfo=UTC)


@pytest.fixture
def conectar(tmp_path: Path) -> Conectar:
    conectar = functools.partial(sqlite3.connect, tmp_path / "tracking.db")
    crear_tabla_infracciones(conectar)
    agregar_columna_proximo_intento(conectar)
    return conectar


@pytest.fixture
def repositorio(conectar: Conectar) -> RepositorioAlertasSQLite:
    return RepositorioAlertasSQLite(conectar)


def _registrar(
    conectar: Conectar, nombre: str | None, zona: str, minuto: int = 0, track_id: int = 1
) -> None:
    incumplimiento = Incumplimiento(track_id, nombre, ElementoEPP.CASCO, zona)
    inicio = INICIO + timedelta(minutes=minuto)
    evento = InfraccionIniciada(incumplimiento, inicio, "epp-0.1.0", evidencia=f"ev/{minuto}.jpg")
    RepositorioInfraccionesSQLite(conectar).guardar(evento)


def _tres_alertas(conectar: Conectar) -> None:
    _registrar(conectar, "Ana", "Boca de pozo", minuto=0, track_id=1)
    _registrar(conectar, None, "Playa de tanques", minuto=1, track_id=2)
    _registrar(conectar, "Luis", "Boca de pozo", minuto=2, track_id=3)


def _reconocimientos(conectar: Conectar) -> list[tuple[object, ...]]:
    with closing(conectar()) as conexion:
        consulta = "SELECT id, reconocida_por, reconocida_en FROM ppe_infracciones ORDER BY id"
        return conexion.execute(consulta).fetchall()


def test_listar_devuelve_las_alertas_de_la_mas_nueva_a_la_mas_vieja(
    conectar: Conectar, repositorio: RepositorioAlertasSQLite
) -> None:
    _tres_alertas(conectar)
    BandejaAvisosSQLite(conectar).marcar_enviada(2)

    alertas = repositorio.listar(zona=None, limite=10)

    assert alertas == [
        AlertaRegistrada(
            3, "Luis", "Boca de pozo", "casco", INICIO + timedelta(minutes=2), "ev/2.jpg",
            EstadoNotificacion.PENDIENTE, None, None,
        ),
        AlertaRegistrada(
            2, None, "Playa de tanques", "casco", INICIO + timedelta(minutes=1), "ev/1.jpg",
            EstadoNotificacion.ENVIADA, None, None,
        ),
        AlertaRegistrada(
            1, "Ana", "Boca de pozo", "casco", INICIO, "ev/0.jpg",
            EstadoNotificacion.PENDIENTE, None, None,
        ),
    ]  # fmt: skip


def test_listar_filtra_por_zona(conectar: Conectar, repositorio: RepositorioAlertasSQLite) -> None:
    _tres_alertas(conectar)

    alertas = repositorio.listar(zona="Boca de pozo", limite=10)

    assert [alerta.id_infraccion for alerta in alertas] == [3, 1]


def test_listar_respeta_el_limite(
    conectar: Conectar, repositorio: RepositorioAlertasSQLite
) -> None:
    _tres_alertas(conectar)

    alertas = repositorio.listar(zona=None, limite=2)

    assert [alerta.id_infraccion for alerta in alertas] == [3, 2]


def test_zonas_con_alertas_sin_repetir_y_ordenadas(
    conectar: Conectar, repositorio: RepositorioAlertasSQLite
) -> None:
    _tres_alertas(conectar)

    assert repositorio.zonas() == ["Boca de pozo", "Playa de tanques"]


def test_reconocer_guarda_quien_y_cuando_en_utc(
    conectar: Conectar, repositorio: RepositorioAlertasSQLite
) -> None:
    _tres_alertas(conectar)
    hora_local = RECIBIDA.astimezone(timezone(timedelta(hours=-3)))

    repositorio.reconocer(2, por="Supervisora", en=hora_local)

    assert _reconocimientos(conectar)[1] == (2, "Supervisora", "2026-10-22T08:30:00+00:00")
    assert repositorio.listar(zona="Playa de tanques", limite=1)[0][-2:] == (
        "Supervisora",
        RECIBIDA,
    )


def test_reconocer_dos_veces_conserva_el_primer_acuse(
    conectar: Conectar, repositorio: RepositorioAlertasSQLite
) -> None:
    _tres_alertas(conectar)
    repositorio.reconocer(2, por="Supervisora", en=RECIBIDA)

    with pytest.raises(
        AlertaNoReconocibleError, match=r"^La alerta 2 no existe o ya fue reconocida$"
    ):
        repositorio.reconocer(2, por="Otro", en=RECIBIDA + timedelta(minutes=1))

    assert _reconocimientos(conectar)[1] == (2, "Supervisora", "2026-10-22T08:30:00+00:00")


def test_reconocer_una_alerta_inexistente_falla(repositorio: RepositorioAlertasSQLite) -> None:
    with pytest.raises(
        AlertaNoReconocibleError, match=r"^La alerta 9 no existe o ya fue reconocida$"
    ):
        repositorio.reconocer(9, por="Supervisora", en=RECIBIDA)


@pytest.mark.parametrize("por", ["", "   "], ids=["vacio", "espacios"])
def test_reconocer_exige_saber_quien_acusa_recibo(
    conectar: Conectar, repositorio: RepositorioAlertasSQLite, por: str
) -> None:
    _tres_alertas(conectar)

    with pytest.raises(ValueError, match=r"^El acuse de recibo necesita quién lo da$"):
        repositorio.reconocer(1, por=por, en=RECIBIDA)

    assert _reconocimientos(conectar)[0] == (1, None, None)


def test_reconocer_rechaza_una_hora_sin_huso_horario(
    conectar: Conectar, repositorio: RepositorioAlertasSQLite
) -> None:
    _tres_alertas(conectar)

    with pytest.raises(ValueError, match=r"^La hora debe tener huso horario: 2026-10-22T08:30:00$"):
        repositorio.reconocer(1, por="Supervisora", en=datetime(2026, 10, 22, 8, 30))


def test_listar_y_reconocer_tratan_la_inyeccion_sql_como_texto(
    conectar: Conectar, repositorio: RepositorioAlertasSQLite
) -> None:
    _registrar(conectar, INYECCION, INYECCION)

    repositorio.reconocer(1, por=INYECCION, en=RECIBIDA)

    (alerta,) = repositorio.listar(zona=INYECCION, limite=5)
    assert (alerta.persona, alerta.zona, alerta.reconocida_por) == (INYECCION,) * 3
    assert repositorio.listar(zona="Boca de pozo", limite=5) == []
