"""DatabaseManager: conexión, migración, fechas y reportes (CLAUDE.md §7, módulo crítico).

Completa tests/test_database_manager.py con lo que la mutación mostró sin fijar.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from freezegun import freeze_time

from src.storage.database_manager import DatabaseManager

AHORA = "2026-10-24 09:15:30.123456"
DIA = "2026-10-24"
OTRO_DIA = "2026-10-23"
MINUTO = 60
HORA = 3600
SALTO_MAXIMO = 300  # segundos sin registros que todavía cuentan como seguimiento continuo
BUSY_TIMEOUT_MS = 30000
SYNCHRONOUS_NORMAL = 1

MARCAS_DE_TIEMPO = (
    "SELECT timestamp FROM tracking",
    "SELECT timestamp FROM snapshots",
    "SELECT timestamp FROM workday_states",
)
NOMBRES_POR_TABLA = (
    "SELECT DISTINCT employee_name FROM tracking",
    "SELECT DISTINCT employee_name FROM snapshots",
    "SELECT DISTINCT employee_name FROM daily_attendance",
    "SELECT DISTINCT employee_name FROM workday_states",
)

Registro = tuple[str, str, int]  # (empleado, timestamp, dentro de la zona)


@pytest.fixture
def db(tmp_path: Path) -> DatabaseManager:
    return DatabaseManager(db_path=str(tmp_path / "db" / "t.db"))


@pytest.fixture
def conexion(db: DatabaseManager) -> Iterator[sqlite3.Connection]:
    conexion = sqlite3.connect(db.db_path)
    yield conexion
    conexion.close()


def _instante(segundos: float, dia: str = DIA) -> str:
    horas, resto = divmod(int(segundos), HORA)
    minutos, segundos_restantes = divmod(resto, MINUTO)
    return f"{dia}T{8 + horas:02d}:{minutos:02d}:{segundos_restantes:02d}"


def _racha(nombre: str, pasos: list[int], dentro: int = 1, dia: str = DIA) -> list[Registro]:
    """Un registro al inicio y otro después de cada paso (en segundos), todos con `dentro`."""
    instantes = [0]
    for paso in pasos:
        instantes.append(instantes[-1] + paso)
    return [(nombre, _instante(t, dia), dentro) for t in instantes]


def _cargar(conexion: sqlite3.Connection, registros: list[Registro]) -> None:
    conexion.executemany(
        "INSERT INTO tracking (employee_name, timestamp, inside_zone) VALUES (?, ?, ?)", registros
    )
    conexion.commit()


def _asistencia(conexion: sqlite3.Connection, llegada: str | None, salida: str | None) -> None:
    conexion.execute(
        "INSERT INTO daily_attendance (employee_name, date, arrival_time, departure_time) "
        "VALUES ('Ana', ?, ?, ?)",
        (DIA, llegada, salida),
    )
    conexion.commit()


# --- Ubicación, conexión y migración --------------------------------------------------------


def test_sin_db_path_usa_la_base_de_appdata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))

    ruta = Path(DatabaseManager().db_path)

    assert ruta == tmp_path / "OficinaEficiencia" / "data" / "db" / "local_tracking.db"
    assert ruta.is_file()


def test_sin_appdata_usa_la_carpeta_personal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # una ruta relativa equivocada también queda en tmp_path
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    ruta = Path(DatabaseManager().db_path)

    assert ruta == tmp_path / "OficinaEficiencia" / "data" / "db" / "local_tracking.db"


def test_la_conexion_usa_wal_synchronous_normal_y_espera_30_s(db: DatabaseManager) -> None:
    conexion = db._get_connection()

    configuracion = [
        conexion.execute("PRAGMA journal_mode").fetchone()[0],
        conexion.execute("PRAGMA synchronous").fetchone()[0],
        conexion.execute("PRAGMA busy_timeout").fetchone()[0],
    ]
    conexion.close()

    assert configuracion == ["wal", SYNCHRONOUS_NORMAL, BUSY_TIMEOUT_MS]


def test_una_base_nueva_agrega_y_avisa_la_columna_de_empleado(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    DatabaseManager(db_path=str(tmp_path / "t.db"))

    assert capsys.readouterr().out == (
        "Adding employee_name column to snapshots table...\n"
        "Adding employee_name column to tracking table...\n"
    )


def test_reabrir_una_base_migrada_no_repite_la_migracion(
    db: DatabaseManager, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()

    DatabaseManager(db_path=db.db_path)

    assert capsys.readouterr().out == ""


# --- Fechas de los registros ----------------------------------------------------------------


@freeze_time(AHORA)
def test_los_registros_guardan_la_hora_actual_en_iso(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    db.insert_record(1, 0.0, 0.0, "A", 1)
    db.insert_snapshot(1, "A", "foto.jpg")
    db.insert_state("Ana", "activo")

    marcas = [conexion.execute(consulta).fetchone()[0] for consulta in MARCAS_DE_TIEMPO]

    assert marcas == ["2026-10-24T09:15:30.123456"] * len(marcas)


def test_la_asistencia_guarda_llegada_y_actualiza_solo_la_salida(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    with freeze_time(f"{DIA} 08:05:09"):
        db.update_attendance("Ana")
    with freeze_time(f"{DIA} 17:30:00"):
        db.update_attendance("Ana")

    fila = conexion.execute(
        "SELECT date, arrival_time, departure_time FROM daily_attendance"
    ).fetchall()

    assert fila == [(DIA, "08:05:09", "17:30:00")]


def test_el_perfil_sin_datos_organizacionales_queda_en_blanco(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    db.save_employee_profile("Ana")

    fila = conexion.execute("SELECT department, position, shift FROM employees").fetchone()

    assert fila == ("", "", "")


# --- Reporte de asistencia ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("llegada", "salida", "horas"),
    [
        ("08:00:00", None, "0.00"),
        (None, "17:00:00", "0.00"),
        ("08:00:00", "08:00:00", "0.00"),
        ("00:00:00", "23:00:00", "23.00"),
        ("22:00:00", "06:00:00", "8.00"),
        ("8am", "17:00:00", "0.00"),
    ],
    ids=[
        "sin_salida",
        "sin_llegada",
        "misma_hora",
        "23_horas",
        "turno_de_noche",
        "formato_invalido",
    ],
)
def test_horas_totales_de_la_asistencia(
    db: DatabaseManager,
    conexion: sqlite3.Connection,
    llegada: str | None,
    salida: str | None,
    horas: str,
) -> None:
    _asistencia(conexion, llegada, salida)

    (fila,) = db.get_attendance_report(DIA, DIA)

    assert fila == ("Ana", DIA, llegada, salida, horas)


def test_el_filtro_todos_de_asistencia_trae_a_todos(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    _asistencia(conexion, "08:00:00", "09:00:00")
    conexion.execute(
        "INSERT INTO daily_attendance (employee_name, date, arrival_time, departure_time) "
        "VALUES ('Luis', ?, '08:00:00', '10:00:00')",
        (DIA,),
    )
    conexion.commit()

    nombres = [fila[0] for fila in db.get_attendance_report(DIA, DIA, "Todos")]

    assert nombres == ["Ana", "Luis"]


# --- Reporte de eficiencia ------------------------------------------------------------------


def test_eficiencia_suma_tiempo_dentro_y_fuera_hasta_el_ultimo_registro(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    _cargar(
        conexion,
        [("Ana", _instante(0), 1), ("Ana", _instante(60), 0), ("Ana", _instante(180), 1)],
    )

    assert db.get_efficiency_report(DIA, DIA) == [("Ana", DIA, "0h 3m", "0h 1m", "33.3%")]


@pytest.mark.parametrize(
    ("pasos", "total", "activo"),
    [
        ([120], "0h 2m", "0h 2m"),
        ([SALTO_MAXIMO] * 12, "1h 0m", "1h 0m"),
        ([SALTO_MAXIMO] * 24 + [MINUTO], "2h 1m", "2h 1m"),
        ([1], "0h 0m", "0h 0m"),
    ],
    ids=["dos_minutos", "una_hora", "dos_horas_un_minuto", "un_segundo"],
)
def test_eficiencia_formatea_horas_y_minutos(
    db: DatabaseManager,
    conexion: sqlite3.Connection,
    pasos: list[int],
    total: str,
    activo: str,
) -> None:
    _cargar(conexion, _racha("Ana", pasos))

    assert db.get_efficiency_report(DIA, DIA) == [("Ana", DIA, total, activo, "100.0%")]


def test_eficiencia_cuenta_un_hueco_de_hasta_5_minutos(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    _cargar(conexion, _racha("Ana", [SALTO_MAXIMO, MINUTO], dentro=0))

    assert db.get_efficiency_report(DIA, DIA) == [("Ana", DIA, "0h 6m", "0h 0m", "0.0%")]


def test_eficiencia_salta_un_hueco_mayor_y_sigue_con_el_resto(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    _cargar(conexion, _racha("Ana", [SALTO_MAXIMO + 1, 2 * MINUTO]))

    assert db.get_efficiency_report(DIA, DIA) == [("Ana", DIA, "0h 2m", "0h 2m", "100.0%")]


def test_un_dia_con_un_solo_registro_no_aparece(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    _cargar(conexion, [("Ana", _instante(0), 1), *_racha("Luis", [MINUTO])])

    assert db.get_efficiency_report(DIA, DIA) == [("Luis", DIA, "0h 1m", "0h 1m", "100.0%")]


def test_un_registro_con_hora_ilegible_se_salta_sin_perder_los_demas(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    _cargar(conexion, [("Ana", f"{DIA} 24:00:00", 1), *_racha("Ana", [2 * MINUTO])])

    assert db.get_efficiency_report(DIA, DIA) == [("Ana", DIA, "0h 2m", "0h 2m", "100.0%")]


def test_eficiencia_ordena_por_fecha_y_nombre_descendentes(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    _cargar(
        conexion,
        _racha("Ana", [MINUTO], dia=OTRO_DIA)
        + _racha("Luis", [MINUTO], dia=OTRO_DIA)
        + _racha("Ana", [MINUTO])
        + _racha("Luis", [MINUTO]),
    )

    claves = [(fila[1], fila[0]) for fila in db.get_efficiency_report(OTRO_DIA, DIA)]

    assert claves == [(DIA, "Luis"), (DIA, "Ana"), (OTRO_DIA, "Luis"), (OTRO_DIA, "Ana")]


@pytest.mark.parametrize(
    ("filtro", "nombres"),
    [("Luis", ["Luis"]), ("Todos", ["Luis", "Ana"]), (None, ["Luis", "Ana"])],
    ids=["un_empleado", "todos", "sin_filtro"],
)
def test_eficiencia_filtra_por_empleado(
    db: DatabaseManager, conexion: sqlite3.Connection, filtro: str | None, nombres: list[str]
) -> None:
    _cargar(conexion, _racha("Ana", [MINUTO]) + _racha("Luis", [MINUTO]))

    filas = db.get_efficiency_report(DIA, DIA, filtro)

    assert [fila[0] for fila in filas] == nombres


# --- Derecho al olvido ----------------------------------------------------------------------


def test_anonimizar_reemplaza_el_nombre_en_las_cuatro_tablas(
    db: DatabaseManager, conexion: sqlite3.Connection
) -> None:
    db.insert_record(1, 0.0, 0.0, "A", 1, employee_name="Ana")
    db.insert_snapshot(1, "A", "foto.jpg", employee_name="Ana")
    db.update_attendance("Ana")
    db.insert_state("Ana", "activo")

    seudonimo = db.anonymize_employee("Ana")
    nombres = [conexion.execute(consulta).fetchall() for consulta in NOMBRES_POR_TABLA]

    assert nombres == [[(seudonimo,)]] * len(nombres)
