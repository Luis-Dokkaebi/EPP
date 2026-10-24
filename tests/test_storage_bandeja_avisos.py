"""Bandeja de salida de avisos sobre ppe_infracciones (SPEC/9 §7.1, §7.4; CLAUDE.md §9)."""

import functools
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.alerts.domain.aviso import Aviso, EstadoNotificacion
from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.infracciones import Incumplimiento, InfraccionIniciada
from src.storage.bandeja_avisos import (
    AvisoNoPendienteError,
    BandejaAvisosSQLite,
    agregar_columna_proximo_intento,
    quitar_columna_proximo_intento,
)
from src.storage.infracciones_epp import RepositorioInfraccionesSQLite, crear_tabla_infracciones
from tests.dobles_ppe import INICIO

Conectar = functools.partial[sqlite3.Connection]
Accion = Callable[[BandejaAvisosSQLite], object]
DIEZ_SEGUNDOS = timedelta(seconds=10)
INYECCION = "x'); DROP TABLE ppe_infracciones; --"


@pytest.fixture
def conectar(tmp_path: Path) -> Conectar:
    conectar = functools.partial(sqlite3.connect, tmp_path / "tracking.db")
    crear_tabla_infracciones(conectar)
    agregar_columna_proximo_intento(conectar)
    return conectar


@pytest.fixture
def bandeja(conectar: Conectar) -> BandejaAvisosSQLite:
    return BandejaAvisosSQLite(conectar)


def _registrar(conectar: Conectar, nombre: str | None = "Ana", track_id: int = 1) -> None:
    incumplimiento = Incumplimiento(track_id, nombre, ElementoEPP.CASCO, "Boca de pozo")
    evento = InfraccionIniciada(incumplimiento, INICIO, "epp-0.1.0", evidencia="ev/1.jpg")
    RepositorioInfraccionesSQLite(conectar).guardar(evento)


def _registrar_varias(conectar: Conectar, cantidad: int) -> None:
    for track_id in range(1, cantidad + 1):
        _registrar(conectar, track_id=track_id)


def _consultar(conectar: Conectar, sql: str) -> list[tuple[object, ...]]:
    with closing(conectar()) as conexion:
        return conexion.execute(sql).fetchall()


def _estado(conectar: Conectar) -> list[tuple[object, ...]]:
    return _consultar(
        conectar,
        "SELECT id, estado_notificacion, intentos_notificacion, proximo_intento "
        "FROM ppe_infracciones ORDER BY id",
    )


def _columnas(conectar: Conectar) -> list[object]:
    return [fila[1] for fila in _consultar(conectar, "PRAGMA table_info(ppe_infracciones)")]


def test_estado_notificacion_usa_los_valores_guardados_en_la_base() -> None:
    assert [estado.value for estado in EstadoNotificacion] == [
        "PENDIENTE",
        "ENVIADA",
        "FALLIDA",
        "DESCARTADA",
    ]


def test_migracion_agrega_la_columna_al_final_y_es_idempotente(conectar: Conectar) -> None:
    _registrar(conectar)

    agregar_columna_proximo_intento(conectar)

    assert _columnas(conectar)[-2:] == ["reconocida_en", "proximo_intento"]
    assert _estado(conectar) == [(1, "PENDIENTE", 0, None)]


def test_migracion_se_revierte_sin_perder_las_infracciones(conectar: Conectar) -> None:
    _registrar(conectar)

    quitar_columna_proximo_intento(conectar)
    quitar_columna_proximo_intento(conectar)

    assert "proximo_intento" not in _columnas(conectar)
    assert _consultar(conectar, "SELECT id, employee_name FROM ppe_infracciones") == [(1, "Ana")]


def test_pendientes_devuelve_los_avisos_en_orden_de_llegada(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar(conectar, nombre="Ana", track_id=1)
    _registrar(conectar, nombre=None, track_id=2)

    avisos = bandeja.pendientes(INICIO)

    assert avisos == [
        Aviso(1, "Ana", "casco", "Boca de pozo", INICIO, "ev/1.jpg", 0),
        Aviso(2, None, "casco", "Boca de pozo", INICIO, "ev/1.jpg", 0),
    ]


def test_pendientes_omite_los_enviados_y_los_fallidos(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar_varias(conectar, 3)
    bandeja.marcar_enviada(1)
    bandeja.marcar_fallida(3, intentos=5)

    avisos = bandeja.pendientes(INICIO)

    assert [aviso.id_aviso for aviso in avisos] == [2]


@pytest.mark.parametrize(
    ("ahora", "esperados"),
    [
        (INICIO + DIEZ_SEGUNDOS - timedelta(microseconds=1), []),
        (INICIO + DIEZ_SEGUNDOS, [(1, 2)]),
        (INICIO + DIEZ_SEGUNDOS + timedelta(microseconds=1), [(1, 2)]),
        (datetime(2026, 10, 22, 5, 0, 10, tzinfo=timezone(timedelta(hours=-3))), [(1, 2)]),
    ],
    ids=["antes-de-tiempo", "justo-a-tiempo", "vencido", "otro-huso-horario"],
)
def test_pendientes_incluye_un_reprogramado_cuando_llega_su_hora(
    conectar: Conectar,
    bandeja: BandejaAvisosSQLite,
    ahora: datetime,
    esperados: list[tuple[int, int]],
) -> None:
    _registrar(conectar)
    bandeja.reprogramar(1, intentos=2, proximo_intento=INICIO + DIEZ_SEGUNDOS)

    avisos = bandeja.pendientes(ahora)

    assert [(aviso.id_aviso, aviso.intentos) for aviso in avisos] == esperados


def test_reprogramar_guarda_los_intentos_y_la_hora_en_utc(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar(conectar)
    huso_argentina = timezone(timedelta(hours=-3))

    bandeja.reprogramar(
        1, intentos=2, proximo_intento=datetime(2026, 10, 22, 5, tzinfo=huso_argentina)
    )

    assert _estado(conectar) == [(1, "PENDIENTE", 2, "2026-10-22T08:00:00.000000+00:00")]


def test_marcar_enviada_cierra_el_aviso_y_borra_el_proximo_intento(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar(conectar)
    bandeja.reprogramar(1, intentos=1, proximo_intento=INICIO)

    bandeja.marcar_enviada(1)

    assert _estado(conectar) == [(1, "ENVIADA", 1, None)]


def test_marcar_fallida_guarda_los_intentos_y_queda_visible(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar(conectar)
    bandeja.reprogramar(1, intentos=4, proximo_intento=INICIO)

    bandeja.marcar_fallida(1, intentos=5)

    assert _estado(conectar) == [(1, "FALLIDA", 5, None)]


@pytest.mark.parametrize(
    "cambiar",
    [
        lambda bandeja: bandeja.marcar_enviada(1),
        lambda bandeja: bandeja.reprogramar(1, intentos=1, proximo_intento=INICIO),
        lambda bandeja: bandeja.marcar_fallida(1, intentos=1),
    ],
    ids=["enviada", "reprogramada", "fallida"],
)
def test_un_aviso_ya_enviado_no_cambia_de_estado(
    conectar: Conectar, bandeja: BandejaAvisosSQLite, cambiar: Accion
) -> None:
    _registrar(conectar)
    bandeja.marcar_enviada(1)

    with pytest.raises(AvisoNoPendienteError, match=r"^El aviso 1 no existe o no está pendiente$"):
        cambiar(bandeja)

    assert _estado(conectar) == [(1, "ENVIADA", 0, None)]


def test_un_aviso_inexistente_no_se_puede_marcar(bandeja: BandejaAvisosSQLite) -> None:
    with pytest.raises(AvisoNoPendienteError, match=r"^El aviso 99 no existe o no está pendiente$"):
        bandeja.marcar_enviada(99)


@pytest.mark.parametrize(
    ("accion", "hora"),
    [
        (lambda bandeja: bandeja.pendientes(datetime(2026, 10, 22, 8)), "2026-10-22T08:00:00"),
        (
            lambda bandeja: bandeja.reprogramar(1, 1, proximo_intento=datetime(2026, 10, 22)),
            "2026-10-22T00:00:00",
        ),
    ],
    ids=["pendientes", "reprogramar"],
)
def test_una_hora_sin_huso_horario_se_rechaza(
    conectar: Conectar, bandeja: BandejaAvisosSQLite, accion: Accion, hora: str
) -> None:
    _registrar(conectar)

    with pytest.raises(ValueError, match=rf"^La hora debe tener huso horario: {hora}$"):
        accion(bandeja)

    assert _estado(conectar) == [(1, "PENDIENTE", 0, None)]


def test_pendientes_trata_los_valores_con_inyeccion_sql_como_texto(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar(conectar, nombre=INYECCION)

    avisos = bandeja.pendientes(INICIO)

    assert [aviso.persona for aviso in avisos] == [INYECCION]
    assert _consultar(conectar, "SELECT COUNT(*) FROM ppe_infracciones") == [(1,)]


# --- Salida del modo sombra (decisión del 24/10/2026: se descartan las del período) ---


def _registrar_a_las(conectar: Conectar, inicio: datetime, track_id: int) -> None:
    incumplimiento = Incumplimiento(track_id, "Ana", ElementoEPP.CASCO, "Boca de pozo")
    evento = InfraccionIniciada(incumplimiento, inicio, "epp-0.1.0", evidencia=None)
    RepositorioInfraccionesSQLite(conectar).guardar(evento)


def test_descartar_las_pendientes_anteriores_al_fin_del_modo_sombra(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar_a_las(conectar, INICIO - DIEZ_SEGUNDOS, track_id=1)
    _registrar_a_las(conectar, INICIO, track_id=2)
    _registrar_a_las(conectar, INICIO + DIEZ_SEGUNDOS, track_id=3)

    descartadas = bandeja.descartar_pendientes_anteriores(INICIO)

    assert descartadas == 1
    assert [fila[:2] for fila in _estado(conectar)] == [
        (1, "DESCARTADA"),
        (2, "PENDIENTE"),
        (3, "PENDIENTE"),
    ]
    assert [aviso.id_aviso for aviso in bandeja.pendientes(INICIO + DIEZ_SEGUNDOS)] == [2, 3]


def test_descartar_no_toca_avisos_enviados_ni_fallidos(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar_varias(conectar, 2)
    bandeja.marcar_enviada(1)
    bandeja.marcar_fallida(2, 5)

    descartadas = bandeja.descartar_pendientes_anteriores(INICIO + DIEZ_SEGUNDOS)

    assert descartadas == 0
    assert [fila[1] for fila in _estado(conectar)] == ["ENVIADA", "FALLIDA"]


def test_descartar_dos_veces_no_descarta_de_nuevo(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar(conectar)
    bandeja.descartar_pendientes_anteriores(INICIO + DIEZ_SEGUNDOS)

    assert bandeja.descartar_pendientes_anteriores(INICIO + DIEZ_SEGUNDOS) == 0


def test_descartar_exige_una_hora_con_huso_horario(bandeja: BandejaAvisosSQLite) -> None:
    with pytest.raises(ValueError, match=r"^La hora debe tener huso horario: 2026-10-22T08:00:00$"):
        bandeja.descartar_pendientes_anteriores(datetime(2026, 10, 22, 8, 0))


def test_descartar_compara_en_utc_aunque_el_limite_venga_en_otro_huso(
    conectar: Conectar, bandeja: BandejaAvisosSQLite
) -> None:
    _registrar(conectar)
    mexico = timezone(timedelta(hours=-6))

    descartadas = bandeja.descartar_pendientes_anteriores(
        (INICIO + DIEZ_SEGUNDOS).astimezone(mexico)
    )

    assert descartadas == 1
