"""Los reportes de la GUI heredada validan el rango de fechas antes de consultar (SPEC/9 §1.11)."""

import importlib
import re
import tkinter as tk
import types
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

# integration y no slow: usan Tk real y el import pesado de la GUI, pero cada prueba es rápida y
# la mutación de src/gui_app.py (que excluye las slow) las necesita.
pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("importacion_sin_efectos")]

AVISO_FECHA = "Fecha inválida: «22/10/2026». Usa el formato AAAA-MM-DD."
FILA = ("Ana", "2026-10-22")


class ArbolFalso:
    def __init__(self) -> None:
        self.filas: list[tuple[str, ...]] = [("vieja",)]

    def get_children(self) -> list[int]:
        return list(range(len(self.filas)))

    def delete(self, _item: int) -> None:
        self.filas.pop()

    def insert(self, _padre: str, _posicion: str, values: tuple[str, ...]) -> None:
        self.filas.append(values)


class BaseDeDatosFalsa:
    def __init__(self) -> None:
        self.consultas: list[tuple[str, str, str, str]] = []

    def get_attendance_report(self, *rango: str) -> list[tuple[str, ...]]:
        self.consultas.append(("asistencia", *rango))
        return [FILA]

    def get_efficiency_report(self, *rango: str) -> list[tuple[str, ...]]:
        self.consultas.append(("eficiencia", *rango))
        return [FILA]


def _campo(texto: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(get=lambda: texto)


@pytest.fixture
def avisos(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    registrados: list[tuple[str, str]] = []
    gui_app = importlib.import_module("src.gui_app")
    monkeypatch.setattr(gui_app.messagebox, "showerror", lambda *a: registrados.append(a))
    return registrados


def _gui(prefijo: str, desde: str) -> Any:
    gui = object.__new__(importlib.import_module("src.gui_app").SystemGUI)
    gui.db = BaseDeDatosFalsa()
    setattr(gui, f"{prefijo}_date_from", _campo(desde))
    setattr(gui, f"{prefijo}_date_to", _campo("2026-10-22"))
    setattr(gui, f"{prefijo}_employee_combo", _campo("Ana"))
    setattr(gui, f"tree_{prefijo}", ArbolFalso())
    return gui


REPORTES = [("att", "generate_attendance_report", "asistencia"),
            ("eff", "generate_efficiency_report", "eficiencia")]  # fmt: skip
NOMBRES = ["asistencia", "eficiencia"]


@pytest.mark.parametrize(
    ("prefijo", "metodo", "reporte"), REPORTES, ids=["asistencia", "eficiencia"]
)
def test_reporte_con_rango_valido_consulta_y_muestra_las_filas(
    prefijo: str, metodo: str, reporte: str, avisos: list[tuple[str, str]]
) -> None:
    gui = _gui(prefijo, desde="2026-10-01")

    getattr(gui, metodo)()

    assert gui.db.consultas == [(reporte, "2026-10-01", "2026-10-22", "Ana")]
    assert getattr(gui, f"tree_{prefijo}").filas == [FILA]
    assert avisos == []


@pytest.mark.parametrize(
    ("prefijo", "metodo", "reporte"), REPORTES, ids=["asistencia", "eficiencia"]
)
def test_reporte_con_fecha_invalida_avisa_y_no_consulta(
    prefijo: str, metodo: str, reporte: str, avisos: list[tuple[str, str]]
) -> None:
    gui = _gui(prefijo, desde="22/10/2026")

    getattr(gui, metodo)()

    assert gui.db.consultas == []
    assert getattr(gui, f"tree_{prefijo}").filas == [("vieja",)]
    assert avisos == [("Rango de fechas inválido", AVISO_FECHA)]


def test_la_app_ya_no_depende_de_tkcalendar() -> None:
    from tests.utilidades_scripts import RAIZ

    requisitos = (RAIZ / "requirements.txt").read_text(encoding="utf-8").lower()
    fuentes = "".join(r.read_text(encoding="utf-8") for r in (RAIZ / "src").rglob("*.py"))

    assert "tkcalendar" not in requisitos
    assert re.search(r"^\s*(from|import)\s+tkcalendar", fuentes, re.MULTILINE) is None


HOY = date(2026, 10, 22)


class FechaFija(date):
    @classmethod
    def today(cls) -> "FechaFija":
        return cls(HOY.year, HOY.month, HOY.day)


@pytest.fixture
def raiz() -> Iterator[tk.Tk]:
    ventana = tk.Tk()
    yield ventana
    ventana.destroy()


@pytest.mark.parametrize(
    ("prefijo", "pestana"),
    [("att", "_build_attendance_tab"), ("eff", "_build_efficiency_tab")],
    ids=NOMBRES,
)
def test_pestana_de_reporte_propone_los_ultimos_siete_dias(
    monkeypatch: pytest.MonkeyPatch, raiz: tk.Tk, prefijo: str, pestana: str
) -> None:
    gui_app = importlib.import_module("src.gui_app")
    monkeypatch.setattr(gui_app, "date", FechaFija)
    gui = object.__new__(gui_app.SystemGUI)
    gui.db = types.SimpleNamespace(get_unique_employees=lambda: [])

    getattr(gui, pestana)(tk.Frame(raiz))

    assert getattr(gui, f"{prefijo}_date_from").get() == "2026-10-15"
    assert getattr(gui, f"{prefijo}_date_to").get() == "2026-10-22"
