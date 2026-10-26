"""Cálculo de visitas por zona (CLAUDE.md §7 y §16: módulo crítico de eficiencia).

Cada visita es una racha de frames dentro de la zona; su duración va del primer al último
frame dentro, y el nombre y la foto salen del snapshot tomado al entrar (menos de 5 s).
"""

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest

from src.analysis.efficiency_calculator import EfficiencyCalculator

COLUMNAS = [
    "track_id",
    "employee_name",
    "zone",
    "start_time",
    "end_time",
    "duration_sec",
    "productivity_score",
    "snapshot_path",
]
DIA = "2026-10-24"

Fila = tuple[int, str, float, float, str, int]


def _base(ruta: Path, filas: list[Fila], fotos: Sequence[tuple[object, ...]] | None = None) -> str:
    conexion = sqlite3.connect(ruta)
    conexion.execute(
        "CREATE TABLE tracking (track_id INTEGER, timestamp TEXT, x REAL, y REAL, "
        "zone TEXT, inside_zone INTEGER)"
    )
    conexion.executemany("INSERT INTO tracking VALUES (?, ?, ?, ?, ?, ?)", filas)
    if fotos is not None:
        conexion.execute(
            "CREATE TABLE snapshots (track_id INTEGER, timestamp TEXT, zone TEXT, "
            "snapshot_path TEXT, employee_name TEXT)"
        )
        conexion.executemany("INSERT INTO snapshots VALUES (?, ?, ?, ?, ?)", fotos)
    conexion.commit()
    conexion.close()
    return str(ruta)


def _hora(segundo: float) -> str:
    instante = pd.Timestamp(f"{DIA} 09:00:00") + pd.Timedelta(seconds=segundo)
    return instante.strftime("%Y-%m-%d %H:%M:%S.%f")


def _quieto(track: int, zona: str, adentro: list[int], desde: float = 0) -> list[Fila]:
    """Un frame por segundo en (1, 1) con la secuencia de dentro/fuera dada."""
    return [(track, _hora(desde + i), 1.0, 1.0, zona, d) for i, d in enumerate(adentro)]


def _calcular(
    tmp_path: Path, filas: list[Fila], fotos: Sequence[tuple[object, ...]] | None = None
) -> pd.DataFrame:
    reporte = EfficiencyCalculator(db_path=_base(tmp_path / "t.db", filas, fotos))
    resultado = reporte.calculate_efficiency()
    assert resultado is not None, "con registros siempre hay reporte"
    return resultado


def test_sin_db_path_usa_la_base_de_appdata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))

    ruta = EfficiencyCalculator().db_path

    assert Path(ruta) == tmp_path / "OficinaEficiencia" / "data" / "db" / "local_tracking.db"


def test_sin_appdata_usa_la_carpeta_personal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    ruta = EfficiencyCalculator().db_path

    assert Path(ruta) == tmp_path / "OficinaEficiencia" / "data" / "db" / "local_tracking.db"


def test_sin_registros_no_hay_reporte_y_lo_avisa(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calculadora = EfficiencyCalculator(db_path=_base(tmp_path / "t.db", []))

    assert calculadora.calculate_efficiency() is None
    assert capsys.readouterr().out == "No hay datos en la base de datos.\n"


def test_sin_tabla_de_snapshots_carga_una_vacia_con_sus_columnas(tmp_path: Path) -> None:
    calculadora = EfficiencyCalculator(db_path=_base(tmp_path / "t.db", _quieto(1, "A", [1])))

    _, fotos = calculadora.load_data()

    assert fotos.empty
    assert list(fotos.columns) == [
        "track_id",
        "timestamp",
        "zone",
        "snapshot_path",
        "employee_name",
    ]


def test_sin_snapshots_la_visita_queda_sin_nombre_ni_foto(tmp_path: Path) -> None:
    reporte = _calcular(tmp_path, _quieto(1, "A", [0, 1, 1, 0]))

    assert list(reporte.columns) == COLUMNAS
    assert reporte[["employee_name", "snapshot_path"]].values.tolist() == [["Unknown", "N/A"]]


def test_cada_entrada_a_la_zona_es_una_visita_aparte(tmp_path: Path) -> None:
    reporte = _calcular(tmp_path, _quieto(1, "A", [1, 1, 0, 0, 1, 1, 1]))

    assert reporte["duration_sec"].tolist() == [1.0, 2.0]
    assert reporte["start_time"].tolist() == [pd.Timestamp(_hora(0)), pd.Timestamp(_hora(4))]
    assert reporte["end_time"].tolist() == [pd.Timestamp(_hora(1)), pd.Timestamp(_hora(6))]


def test_un_solo_frame_afuera_separa_dos_visitas(tmp_path: Path) -> None:
    reporte = _calcular(tmp_path, _quieto(1, "A", [1, 0, 1]))

    assert reporte["start_time"].tolist() == [pd.Timestamp(_hora(0)), pd.Timestamp(_hora(2))]


def test_un_grupo_sin_visitas_no_corta_los_demas(tmp_path: Path) -> None:
    filas = _quieto(1, "A", [0, 0]) + _quieto(1, "B", [1, 1]) + _quieto(2, "A", [1, 1])

    reporte = _calcular(tmp_path, filas)

    assert reporte[["track_id", "zone"]].values.tolist() == [[1, "B"], [2, "A"]]


def test_una_visita_de_un_solo_frame_dura_cero_y_no_tiene_actividad(tmp_path: Path) -> None:
    reporte = _calcular(tmp_path, _quieto(1, "A", [0, 1, 0]))

    assert reporte[["duration_sec", "productivity_score"]].values.tolist() == [[0.0, 0.0]]


def test_la_actividad_es_la_suma_de_desvios_redondeada_a_dos_decimales(tmp_path: Path) -> None:
    filas = [(1, _hora(0), 0.0, 0.0, "A", 1), (1, _hora(0.0015), 1.0, 0.0, "A", 1)]

    reporte = _calcular(tmp_path, filas)

    assert reporte["productivity_score"].tolist() == [0.71]
    assert reporte["duration_sec"].tolist() == [0.0]


@pytest.mark.parametrize(
    ("segundos", "nombre", "foto"),
    [
        (0, "Ana", "ana.jpg"),
        (4.9, "Ana", "ana.jpg"),
        (5, "Unknown", "N/A"),
        (5.5, "Unknown", "N/A"),
    ],
    ids=["al_entrar", "casi_5_s", "justo_5_s", "mas_de_5_s"],
)
def test_el_snapshot_cuenta_solo_si_es_de_menos_de_5_s_desde_la_entrada(
    tmp_path: Path, segundos: float, nombre: str, foto: str
) -> None:
    fotos = [(1, _hora(1 + segundos), "A", "ana.jpg", "Ana")]

    reporte = _calcular(tmp_path, _quieto(1, "A", [0, 1, 1]), fotos)

    assert reporte[["employee_name", "snapshot_path"]].values.tolist() == [[nombre, foto]]


def test_el_snapshot_de_otra_persona_en_la_misma_zona_no_cuenta(tmp_path: Path) -> None:
    fotos = [(2, _hora(1), "A", "otro.jpg", "Otro")]

    reporte = _calcular(tmp_path, _quieto(1, "A", [0, 1, 1]), fotos)

    assert reporte[["employee_name", "snapshot_path"]].values.tolist() == [["Unknown", "N/A"]]


@pytest.mark.parametrize("nombre", [None, "   "], ids=["nulo", "en_blanco"])
def test_un_snapshot_sin_nombre_deja_la_visita_como_desconocida(
    tmp_path: Path, nombre: str | None
) -> None:
    fotos = [(1, _hora(1), "A", "foto.jpg", nombre)]

    reporte = _calcular(tmp_path, _quieto(1, "A", [0, 1, 1]), fotos)

    assert reporte[["employee_name", "snapshot_path"]].values.tolist() == [["Unknown", "foto.jpg"]]
