"""El botón "Importar carpeta con consentimientos" de Gestión de Empleados (SPEC/10 T-15)."""

import getpass
import tkinter.filedialog
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import customtkinter as ctk
import pytest

from config import config
from config.path_utils import ConfigManager
from src.gui import importacion_rostros_gui, views

# Crea ventanas de Tk: necesita pantalla, fuera del hook rápido (como tests/test_vistas_epp.py).
pytestmark = pytest.mark.integration

BOTON = "Importar carpeta con consentimientos"
GRIS = "#A0A0A0"
ALTO_DEL_BOTON = 38


class RostrosFalsos:
    """Doble de FaceRecognizer: toda foto tiene rostro."""

    def __init__(self, faces_dir: str) -> None:
        self.faces_dir = faces_dir
        self.known_face_names: list[str] = []

    def register_face_burst(self, image_paths: list[str], name: str) -> int:
        self.known_face_names.append(name)
        return len(image_paths)


@pytest.fixture
def raiz() -> Iterator[ctk.CTk]:
    raiz = ctk.CTk()
    raiz.withdraw()
    yield raiz
    raiz.destroy()


@pytest.fixture
def vista(raiz: ctk.CTk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ctk.CTkFrame:
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(ConfigManager, "_active_tenant_id", "Planta")
    monkeypatch.setattr(getpass, "getuser", lambda: "supervisor")
    monkeypatch.setattr("src.recognition.face_recognizer.FaceRecognizer", RostrosFalsos)
    monkeypatch.setattr(config, "get_faces_dir", lambda: str(tmp_path / "faces"))
    monkeypatch.setattr(config, "get_db_path", lambda: str(tmp_path / "sucursal.db"))
    return views.create_employees_view(raiz, raiz)


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    origen = tmp_path / "rostros_acme"
    (origen / "Ana Lopez").mkdir(parents=True)
    (origen / "Ana Lopez" / "a.jpg").write_bytes(b"foto")
    (origen / "Pedro Gil").mkdir()
    (origen / "consentimientos.csv").write_text(
        "nombre,id_consentimiento\nAna Lopez,C-001\n", encoding="utf-8"
    )
    return origen


def _hijos(widget: Any) -> list[Any]:
    hijos = []
    for hijo in widget.winfo_children():
        hijos.append(hijo)
        hijos.extend(_hijos(hijo))
    return hijos


def _boton(vista: ctk.CTkFrame) -> ctk.CTkButton:
    (boton,) = (
        h for h in _hijos(vista) if isinstance(h, ctk.CTkButton) and h.cget("text") == BOTON
    )
    return boton


def _etiquetas(vista: ctk.CTkFrame) -> dict[str, str]:
    return {
        str(h.cget("text")): str(h.cget("text_color"))
        for h in _hijos(vista)
        if isinstance(h, ctk.CTkLabel)
    }


def test_el_boton_de_importar_esta_bajo_el_de_subir_archivo(vista: ctk.CTkFrame) -> None:
    boton = _boton(vista)
    botones = [h.cget("text") for h in boton.master.pack_slaves() if isinstance(h, ctk.CTkButton)]
    empaque = boton.pack_info()

    assert botones[:2] == ["📁 Subir Archivo y Registrar", BOTON]
    assert boton.cget("height") == ALTO_DEL_BOTON
    assert (empaque["pady"], empaque["padx"], empaque["fill"]) == (5, 15, "x")


def test_importar_muestra_el_resumen_y_actualiza_la_lista_de_empleados(
    vista: ctk.CTkFrame, carpeta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    titulos: list[str] = []
    monkeypatch.setattr(
        tkinter.filedialog, "askdirectory", lambda title: titulos.append(title) or str(carpeta)
    )

    _boton(vista).invoke()

    etiquetas = _etiquetas(vista)
    resumen = "Cargados: 1 (Ana Lopez). Omitidos: Pedro Gil (sin consentimiento registrado)."
    assert etiquetas[resumen] == GRIS
    assert "  👤 Ana Lopez" in etiquetas
    assert "No hay empleados registrados." not in etiquetas
    assert titulos == ["Carpeta de rostros con consentimientos.csv"]


def test_cancelar_la_eleccion_de_carpeta_no_cambia_nada(
    vista: ctk.CTkFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tkinter.filedialog, "askdirectory", lambda title: "")
    antes = _etiquetas(vista)

    _boton(vista).invoke()

    assert _etiquetas(vista) == antes
    assert "No hay empleados registrados." in antes


def test_elegir_e_importar_devuelve_none_si_se_cancela(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tkinter.filedialog, "askdirectory", lambda title: "")

    assert importacion_rostros_gui.elegir_e_importar(object(), object()) is None
