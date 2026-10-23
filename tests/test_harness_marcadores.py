"""Harness: el marcador `unit` se asigna solo y permite el hook rápido `-m unit`."""

import pytest


def test_marcadores_prueba_sin_tipo_se_marca_como_unitaria(request: pytest.FixtureRequest) -> None:
    marcador = request.node.get_closest_marker("unit")

    assert marcador is not None


@pytest.mark.slow
def test_marcadores_prueba_lenta_no_se_marca_como_unitaria(request: pytest.FixtureRequest) -> None:
    marcador = request.node.get_closest_marker("unit")

    assert marcador is None
