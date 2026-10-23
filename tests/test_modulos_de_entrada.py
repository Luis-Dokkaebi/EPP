"""Humo: los módulos de entrada heredados importan con el prefijo `src.` (A-04)."""

import importlib
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def importacion_sin_efectos(monkeypatch: pytest.MonkeyPatch) -> None:
    # src/gui_app.py reemplaza sys.excepthook y src/main.py fija una variable de entorno.
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.delenv("KMP_DUPLICATE_LIB_OK", raising=False)
    # face_recognition (dlib) solo existe en Windows; en Linux se usa un doble.
    monkeypatch.setitem(
        sys.modules, "face_recognition", sys.modules.get("face_recognition") or MagicMock()
    )


@pytest.mark.slow
@pytest.mark.usefixtures("importacion_sin_efectos")
@pytest.mark.parametrize(
    ("modulo", "atributo"),
    [
        ("src.main", "start_video_stream"),
        ("src.gui_app", "SystemGUI"),
        ("src.analysis.report_main", "generar_reporte"),
    ],
)
def test_modulo_de_entrada_importa_con_el_prefijo_src(modulo: str, atributo: str) -> None:
    importado = importlib.import_module(modulo)

    assert callable(getattr(importado, atributo))
