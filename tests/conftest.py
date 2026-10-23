"""Configuración compartida de pytest."""

import pytest

MARCADORES_DE_TIPO = frozenset({"bdd", "integration", "slow", "windows"})


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Marca como `unit` toda prueba sin otro marcador de tipo (CLAUDE.md §4)."""
    for item in items:
        if not MARCADORES_DE_TIPO.intersection(m.name for m in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
