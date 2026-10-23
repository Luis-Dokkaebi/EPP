"""
Regresión CR-02 (OWASP A03): la exportación de reportes debe usar parámetros
enlazados, no interpolación por f-string del input de la GUI. Un payload clásico
de inyección en el campo de fecha NO debe volcar toda la tabla.
"""
import os
import re
import sys
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import pandas as pd
import pytest
from src.storage.database_manager import DatabaseManager
from src.analysis.report_generator import DatabaseWorker

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# La exportación corre en un hilo: se espera un evento (sin sondear con sleep, CLAUDE.md §4).
# En la CI de Windows el primer import de openpyxl tardaba más que el sondeo de 2.5 s.
SEGUNDOS_MAXIMOS = 30


def _avisar(done, **resultado):
    done.update(resultado)
    done["listo"].set()


def _esperar(done):
    assert done["listo"].wait(SEGUNDOS_MAXIMOS), "la exportación no terminó"


@pytest.fixture
def db(tmp_path):
    d = DatabaseManager(db_path=str(tmp_path / "db" / "t.db"))
    # Sembrar filas en dos fechas distintas escribiendo el timestamp directamente.
    conn = d._get_connection()
    conn.execute("INSERT INTO tracking (track_id, timestamp, x, y, zone, inside_zone, employee_name) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)", (1, "2026-03-15T10:00:00", 1, 2, "Z", 1, "Alice"))
    conn.execute("INSERT INTO tracking (track_id, timestamp, x, y, zone, inside_zone, employee_name) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)", (2, "2026-09-20T10:00:00", 1, 2, "Z", 1, "Bob"))
    conn.commit()
    conn.close()
    return d


def test_parametrized_export_respects_range(db, tmp_path):
    """La exportación parametrizada debe respetar el rango de fechas."""
    worker = DatabaseWorker(db)
    out = str(tmp_path / "rep.xlsx")
    done = {"listo": threading.Event()}
    query = ("SELECT employee_name, date(timestamp) as fecha, zone, inside_zone "
             "FROM tracking WHERE date(timestamp) BETWEEN ? AND ?")
    worker.generate_excel_async(query, out,
                                on_success=lambda p, n: _avisar(done, rows=n),
                                on_error=lambda e: _avisar(done, err=e),
                                params=("2026-01-01", "2026-06-30"))
    _esperar(done)
    assert done.get("rows") == 1, f"se esperaba solo la fila dentro de rango, se obtuvo {done}"
    df = pd.read_excel(out)
    assert list(df["employee_name"]) == ["Alice"]


def test_injection_payload_is_inert_with_params(db, tmp_path):
    """Un payload de tautología que vuelca la tabla bajo f-string NO debe hacerlo con params.

    Con end = "1900-01-01' OR '1'='1":
      - f-string  -> ... BETWEEN '2026-01-01' AND '1900-01-01' OR '1'='1'  (tautología -> 2 filas)
      - params    -> el límite superior es el string literal, ninguna fecha coincide  (-> 0 filas)
    """
    payload_end = "1900-01-01' OR '1'='1"

    # Demostrar la vulnerabilidad VIEJA que el fix elimina (la tautología vuelca todo).
    conn = db._get_connection()
    vulnerable = ("SELECT * FROM tracking WHERE date(timestamp) BETWEEN "
                  f"'2026-01-01' AND '{payload_end}'")
    vuln_rows = len(pd.read_sql_query(vulnerable, conn))
    conn.close()
    assert vuln_rows == 2, "sanity: la interpolación por f-string es una tautología (el bug)"

    # La ruta corregida: params enlazados -> el payload es un literal inerte -> 0 filas.
    worker = DatabaseWorker(db)
    out = str(tmp_path / "rep2.xlsx")
    done = {"listo": threading.Event()}
    query = ("SELECT employee_name, date(timestamp) as fecha, zone, inside_zone "
             "FROM tracking WHERE date(timestamp) BETWEEN ? AND ?")
    worker.generate_excel_async(query, out,
                                on_success=lambda p, n: _avisar(done, rows=n),
                                on_error=lambda e: _avisar(done, err=e),
                                params=("2026-01-01", payload_end))
    _esperar(done)
    assert done.get("rows") == 0, f"la inyección filtró filas vía params: {done}"


def test_date_validation_regex_rejects_injection():
    """El regex de validación de fecha debe rechazar payloads de inyección."""
    assert _DATE_RE.match("2026-12-31")
    assert not _DATE_RE.match("2026-12-31' OR '1'='1")
    assert not _DATE_RE.match("2026/12/31")
