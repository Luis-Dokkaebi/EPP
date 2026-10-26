"""Las vistas del módulo de EPP en la ventana principal (SPEC/9 §8.2 y §8.4)."""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import customtkinter as ctk
import pytest

from config import config
from src.gui import epp_en_la_app
from src.gui.panel_alertas import PanelAlertas
from src.gui.vistas_epp import PanelReporteCumplimiento


@pytest.fixture
def sucursal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "get_db_path", lambda: str(tmp_path / "tenant.db"))
    return tmp_path


class RegistroDeVistas:
    def __init__(self) -> None:
        self.vistas: dict[str, object] = {}

    def register_view(self, name: str, view_instance: object) -> None:
        self.vistas[name] = view_instance


@pytest.fixture
def raiz() -> Iterator[ctk.CTk]:
    raiz = ctk.CTk()
    raiz.withdraw()
    yield raiz
    raiz.destroy()


def _esperar_el_reporte() -> None:
    for hilo in threading.enumerate():
        if hilo.name == "reporte-cumplimiento-epp":
            hilo.join()


@pytest.mark.integration
def test_las_vistas_de_alertas_y_cumplimiento_quedan_registradas_sobre_la_base(
    sucursal: Path, monkeypatch: pytest.MonkeyPatch, raiz: ctk.CTk
) -> None:
    monkeypatch.setattr(config, "get_export_dir", lambda: str(sucursal / "export"))
    registro = RegistroDeVistas()

    epp_en_la_app.registrar_vistas(registro, raiz)

    assert list(registro.vistas) == ["AlertasEPP", "CumplimientoEPP"]
    assert isinstance(registro.vistas["AlertasEPP"], PanelAlertas)
    assert isinstance(registro.vistas["CumplimientoEPP"], PanelReporteCumplimiento)
    with closing(sqlite3.connect(sucursal / "tenant.db")) as conexion:
        tablas = conexion.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        assert ("ppe_infracciones",) in tablas.fetchall()


@pytest.mark.integration
def test_el_reporte_de_cumplimiento_se_exporta_a_la_carpeta_de_la_sucursal(
    sucursal: Path, monkeypatch: pytest.MonkeyPatch, raiz: ctk.CTk
) -> None:
    monkeypatch.setattr(config, "get_export_dir", lambda: str(sucursal))
    registro = RegistroDeVistas()
    epp_en_la_app.registrar_vistas(registro, raiz)
    panel = registro.vistas["CumplimientoEPP"]
    assert isinstance(panel, PanelReporteCumplimiento)

    panel.exportar()
    _esperar_el_reporte()

    assert len(list(sucursal.glob("Cumplimiento_EPP_*.xlsx"))) == 1
