"""Vista «Reportes Históricos» con Tk real: el aviso de fin llega por el hilo de la interfaz.

Regresión de la prueba de humo del 24/10/2026: «Exportar Excel» cerraba la aplicación porque el
aviso se dibujaba desde el hilo de la exportación. Integración: necesita una pantalla (el gate
corre la suite bajo xvfb).
"""

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import customtkinter as ctk
import pytest

from config import config
from src.gui import views

pytestmark = pytest.mark.integration

NOMBRE_DEL_HILO = "DB_Excel_Export"
ARCHIVO_DEL_REPORTE = "Reporte_2026-01-01_a_2026-12-31.xlsx"


@pytest.fixture
def raiz() -> Iterator[ctk.CTk]:
    raiz = ctk.CTk()
    raiz.withdraw()
    yield raiz
    raiz.destroy()


@pytest.fixture
def hilos_de_configure(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Anota el hilo de cada `configure` de etiqueta; fuera del hilo principal no toca Tk."""
    hilos: list[str] = []
    original = ctk.CTkLabel.configure

    def configure_espia(self: ctk.CTkLabel, *argumentos: Any, **opciones: Any) -> None:
        hilos.append(threading.current_thread().name)
        if threading.current_thread() is threading.main_thread():
            original(self, *argumentos, **opciones)

    monkeypatch.setattr(ctk.CTkLabel, "configure", configure_espia)
    return hilos


@pytest.fixture
def vista(raiz: ctk.CTk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ctk.CTkFrame:
    monkeypatch.setattr(config, "get_db_path", lambda: str(tmp_path / "db" / "t.db"))
    monkeypatch.setattr(config, "get_export_dir", lambda: str(tmp_path))
    return views.create_reports_view(raiz)


def _hijos(widget: Any) -> list[Any]:
    hijos = []
    for hijo in widget.winfo_children():
        hijos.append(hijo)
        hijos.extend(_hijos(hijo))
    return hijos


def _exportar(vista: ctk.CTkFrame) -> None:
    (boton,) = (h for h in _hijos(vista) if isinstance(h, ctk.CTkButton))
    boton.invoke()
    for hilo in threading.enumerate():
        if hilo.name == NOMBRE_DEL_HILO:
            hilo.join()


def _textos(vista: ctk.CTkFrame) -> list[str]:
    return [str(h.cget("text")) for h in _hijos(vista) if isinstance(h, ctk.CTkLabel)]


def test_exportar_no_toca_la_interfaz_desde_el_hilo_de_la_exportacion(
    vista: ctk.CTkFrame, hilos_de_configure: list[str]
) -> None:
    _exportar(vista)

    assert set(hilos_de_configure) == {threading.main_thread().name}


def test_el_aviso_de_fin_aparece_al_atender_el_buzon(vista: ctk.CTkFrame, tmp_path: Path) -> None:
    _exportar(vista)

    vista.buzon.atender()

    assert (tmp_path / ARCHIVO_DEL_REPORTE).is_file()
    assert any(t.startswith("✅ Reporte exportado:") and "(0 filas)" in t for t in _textos(vista))


def test_el_aviso_de_error_aparece_al_atender_el_buzon(vista: ctk.CTkFrame, tmp_path: Path) -> None:
    (tmp_path / ARCHIVO_DEL_REPORTE).mkdir()
    _exportar(vista)

    vista.buzon.atender()

    assert any(t.startswith("❌ Error:") for t in _textos(vista))
