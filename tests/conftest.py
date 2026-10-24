"""Configuración compartida de pytest."""

import gc
import os
import sys
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from tests import higiene_tk, prueba_en_curso

MARCADORES_DE_TIPO = frozenset({"bdd", "integration", "slow", "windows"})


def pytest_configure(config: pytest.Config) -> None:
    higiene_tk.instalar()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item) -> Iterator[None]:
    """Tras una prueba que creó un Tk, recolecta su basura en el hilo principal (issue #37).

    Si no, un ciclo con objetos de Tk (p. ej. tkinter.font.Font) se libera cuando el recolector
    corre en un hilo de trabajo de otra prueba, su __del__ llama a Tcl desde ese hilo y queda
    esperando al hilo principal, que a su vez espera al hilo: la CI de Linux se colgó así en
    test_report_sql_injection.
    """
    antes = higiene_tk.interpretes_creados()
    yield
    if higiene_tk.interpretes_creados() != antes:
        gc.collect()


def pytest_runtest_logstart(nodeid: str) -> None:
    prueba_en_curso.anotar(nodeid, os.environ)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Marca como `unit` toda prueba sin otro marcador de tipo (CLAUDE.md §4)."""
    for item in items:
        if not MARCADORES_DE_TIPO.intersection(m.name for m in item.iter_markers()):
            item.add_marker(pytest.mark.unit)


@pytest.fixture
def importacion_sin_efectos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importa los módulos de entrada heredados sin dejar efectos globales."""
    # src/gui_app.py reemplaza sys.excepthook y src/main.py fija una variable de entorno.
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.delenv("KMP_DUPLICATE_LIB_OK", raising=False)
    # face_recognition (dlib) solo existe en Windows; en Linux se usa un doble.
    monkeypatch.setitem(
        sys.modules, "face_recognition", sys.modules.get("face_recognition") or MagicMock()
    )
