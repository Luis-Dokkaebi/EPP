"""Humo: los módulos de entrada heredados importan con el prefijo `src.` (A-04)."""

import importlib

import pytest


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
