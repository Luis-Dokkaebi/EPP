import sqlite3
import pytest
from datetime import datetime

from src.storage.database_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    return DatabaseManager(db_path=str(db_dir / "test.db"))


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_all_tables_created(db):
    conn = sqlite3.connect(db.db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in c.fetchall()}
    conn.close()
    expected = {"tracking", "snapshots", "daily_attendance", "workday_states", "employees"}
    assert expected.issubset(tables)


# ---------------------------------------------------------------------------
# insert_record / get_all_records
# ---------------------------------------------------------------------------

def test_insert_record_stores_data(db):
    db.insert_record(track_id=1, x=100.0, y=200.0, zone="Zona_A", inside_zone=1, employee_name="Juan")
    rows = db.get_all_records()
    assert len(rows) == 1
    assert rows[0][1] == 1        # track_id
    assert rows[0][3] == 100.0    # x
    assert rows[0][4] == 200.0    # y
    assert rows[0][5] == "Zona_A"
    assert rows[0][6] == 1        # inside_zone


def test_insert_multiple_records(db):
    for i in range(5):
        db.insert_record(track_id=i, x=float(i), y=float(i), zone="Z", inside_zone=0)
    assert len(db.get_all_records()) == 5


# ---------------------------------------------------------------------------
# insert_snapshot
# ---------------------------------------------------------------------------

def test_insert_snapshot_stores_all_fields(db):
    db.insert_snapshot(track_id=1, zone="Zona_A", snapshot_path="/tmp/snap.jpg", employee_name="Ana")
    conn = sqlite3.connect(db.db_path)
    c = conn.cursor()
    c.execute("SELECT track_id, zone, snapshot_path, employee_name FROM snapshots")
    row = c.fetchone()
    conn.close()
    assert row == (1, "Zona_A", "/tmp/snap.jpg", "Ana")


# ---------------------------------------------------------------------------
# insert_state
# ---------------------------------------------------------------------------

def test_insert_state_stores_employee_and_state(db):
    db.insert_state(employee_name="Pedro", state="Activo")
    conn = sqlite3.connect(db.db_path)
    c = conn.cursor()
    c.execute("SELECT employee_name, state FROM workday_states")
    row = c.fetchone()
    conn.close()
    assert row == ("Pedro", "Activo")


# ---------------------------------------------------------------------------
# update_attendance
# ---------------------------------------------------------------------------

def test_update_attendance_creates_new_record(db):
    db.update_attendance("Maria")
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(db.db_path)
    c = conn.cursor()
    c.execute("SELECT employee_name, date FROM daily_attendance")
    row = c.fetchone()
    conn.close()
    assert row == ("Maria", today)


def test_update_attendance_single_record_per_day(db):
    db.update_attendance("Carlos")
    db.update_attendance("Carlos")
    conn = sqlite3.connect(db.db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM daily_attendance WHERE employee_name='Carlos'")
    count = c.fetchone()[0]
    conn.close()
    assert count == 1


# ---------------------------------------------------------------------------
# employee_exists
# ---------------------------------------------------------------------------

def test_employee_exists_false_when_not_registered(db):
    assert db.employee_exists("Nadie") is False


def test_employee_exists_true_after_save(db):
    db.save_employee_profile("Luis", department="IT")
    assert db.employee_exists("Luis") is True


def test_employee_exists_case_insensitive(db):
    db.save_employee_profile("Carmen")
    assert db.employee_exists("carmen") is True
    assert db.employee_exists("CARMEN") is True


# ---------------------------------------------------------------------------
# save_employee_profile / get_all_employee_names
# ---------------------------------------------------------------------------

def test_get_all_employee_names_contains_saved_employee(db):
    db.save_employee_profile("Sofia", department="RRHH", position="Manager", shift="Mañana")
    assert "Sofia" in db.get_all_employee_names()


def test_get_all_employee_names_sorted_alphabetically(db):
    db.save_employee_profile("Zara")
    db.save_employee_profile("Alba")
    names = db.get_all_employee_names()
    assert names == sorted(names)


def test_save_employee_profile_upsert_no_duplicates(db):
    db.save_employee_profile("Roberto", department="IT")
    db.save_employee_profile("Roberto", department="Ventas")
    assert db.get_all_employee_names().count("Roberto") == 1


# ---------------------------------------------------------------------------
# get_attendance_report
# ---------------------------------------------------------------------------

def test_get_attendance_report_calculates_hours(db):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(db.db_path)
    conn.execute(
        "INSERT INTO daily_attendance (employee_name, date, arrival_time, departure_time) VALUES (?,?,?,?)",
        ("Elena", today, "09:00:00", "17:00:00"),
    )
    conn.commit()
    conn.close()

    report = db.get_attendance_report(today, today)
    assert len(report) == 1
    emp_name, _, _, _, total_hours = report[0]
    assert emp_name == "Elena"
    assert total_hours == "8.00"


def test_get_attendance_report_overnight_shift(db):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(db.db_path)
    conn.execute(
        "INSERT INTO daily_attendance (employee_name, date, arrival_time, departure_time) VALUES (?,?,?,?)",
        ("Noche", today, "22:00:00", "06:00:00"),
    )
    conn.commit()
    conn.close()

    report = db.get_attendance_report(today, today)
    assert float(report[0][4]) == pytest.approx(8.0)


def test_get_attendance_report_filters_by_employee(db):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(db.db_path)
    conn.executemany(
        "INSERT INTO daily_attendance (employee_name, date, arrival_time, departure_time) VALUES (?,?,?,?)",
        [("A", today, "08:00:00", "16:00:00"), ("B", today, "08:00:00", "16:00:00")],
    )
    conn.commit()
    conn.close()

    report = db.get_attendance_report(today, today, employee_name_filter="A")
    assert all(row[0] == "A" for row in report)


# ---------------------------------------------------------------------------
# get_employee_snapshots
# ---------------------------------------------------------------------------

def test_get_employee_snapshots_returns_paths(db):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(db.db_path)
    conn.execute(
        "INSERT INTO snapshots (track_id, timestamp, zone, snapshot_path, employee_name) VALUES (?,?,?,?,?)",
        (1, f"{today}T10:00:00", "Z", "/tmp/a.jpg", "Tomas"),
    )
    conn.commit()
    conn.close()

    paths = db.get_employee_snapshots("Tomas", today)
    assert paths == ["/tmp/a.jpg"]


def test_get_employee_snapshots_empty_for_unknown_employee(db):
    today = datetime.now().strftime("%Y-%m-%d")
    assert db.get_employee_snapshots("Inexistente", today) == []


# ---------------------------------------------------------------------------
# anonymize_employee
# ---------------------------------------------------------------------------

def test_anonymize_employee_replaces_name_in_all_tables(db):
    db.insert_state("Victor", "Activo")
    db.insert_record(track_id=1, x=0, y=0, zone="Z", inside_zone=1, employee_name="Victor")

    anon_id = db.anonymize_employee("Victor")

    assert anon_id.startswith("empleado_eliminado_")
    conn = sqlite3.connect(db.db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM workday_states WHERE employee_name='Victor'")
    assert c.fetchone()[0] == 0
    c.execute("SELECT COUNT(*) FROM tracking WHERE employee_name='Victor'")
    assert c.fetchone()[0] == 0
    conn.close()


# ---------------------------------------------------------------------------
# delete_employee_profile
# ---------------------------------------------------------------------------

def test_delete_employee_profile_removes_from_employees_table(db):
    db.save_employee_profile("Deleteme")
    assert db.employee_exists("Deleteme") is True
    db.delete_employee_profile("Deleteme")
    assert db.employee_exists("Deleteme") is False


# ---------------------------------------------------------------------------
# OWASP A03 — Resistencia a SQL Injection (queries parametrizadas)
# ---------------------------------------------------------------------------

def test_injection_in_employee_name_stored_literally(db):
    """OWASP A03: chars SQL especiales en employee_name se almacenan sin ejecutarse."""
    payload = "'; DROP TABLE tracking; --"
    db.insert_record(track_id=99, x=0, y=0, zone="Z", inside_zone=0, employee_name=payload)
    rows = db.get_all_records()
    # La tabla tracking sigue existiendo y el nombre se guardó verbatim
    assert len(rows) == 1
    assert rows[0][7] == payload


def test_injection_in_employee_exists_returns_false(db):
    """OWASP A03: Intentos de inyección en employee_exists no devuelven True."""
    db.save_employee_profile("Admin")
    assert db.employee_exists("' OR '1'='1") is False
    assert db.employee_exists("Admin' --") is False


def test_injection_in_attendance_filter_returns_no_rows(db):
    """OWASP A03: Inyección en filtro del reporte no expone datos de otros empleados."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(db.db_path)
    conn.executemany(
        "INSERT INTO daily_attendance (employee_name, date, arrival_time, departure_time) VALUES (?,?,?,?)",
        [("Alice", today, "08:00:00", "16:00:00"), ("Bob", today, "08:00:00", "16:00:00")],
    )
    conn.commit()
    conn.close()

    # Con queries parametrizadas este payload no debe coincidir con ningún nombre real
    report = db.get_attendance_report(today, today, employee_name_filter="Alice' OR '1'='1")
    assert len(report) == 0
