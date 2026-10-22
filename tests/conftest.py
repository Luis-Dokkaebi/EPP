"""Configuración compartida de pytest."""

import sys
from unittest.mock import MagicMock

import pytest

MARCADORES_DE_TIPO = frozenset({"bdd", "integration", "slow", "windows"})


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
