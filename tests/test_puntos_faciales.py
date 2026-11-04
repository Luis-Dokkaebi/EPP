"""Modo demostración: dibuja los 5 puntos de referencia de cada cara sobre el cuadro."""

import dataclasses

import numpy as np
import pytest

from src.gui.puntos_faciales import COLOR_DE_PUNTO, dibujar_puntos_faciales
from src.recognition.ports import CaraLocalizada


def _cara(*puntos: tuple[float, float]) -> CaraLocalizada:
    return CaraLocalizada(0.0, 0.0, 10.0, 10.0, puntos, 0.9)


def test_cada_punto_de_cada_cara_queda_pintado() -> None:
    cuadro = np.zeros((40, 40, 3), dtype=np.uint8)

    dibujar_puntos_faciales(cuadro, [_cara((5.2, 6.7)), _cara((30.0, 20.0), (10.0, 35.0))])

    assert tuple(cuadro[7, 5]) == COLOR_DE_PUNTO
    assert tuple(cuadro[20, 30]) == COLOR_DE_PUNTO
    assert tuple(cuadro[35, 10]) == COLOR_DE_PUNTO


def test_sin_caras_el_cuadro_no_cambia() -> None:
    cuadro = np.zeros((10, 10, 3), dtype=np.uint8)

    dibujar_puntos_faciales(cuadro, [])

    assert not cuadro.any()


CELESTE_NEON_BGR = (255, 200, 50)


def test_el_punto_es_celeste_neon_y_relleno_con_radio_de_dos_pixeles() -> None:
    cuadro = np.zeros((20, 20, 3), dtype=np.uint8)

    dibujar_puntos_faciales(cuadro, [_cara((10.0, 10.0))])

    assert tuple(cuadro[10, 10]) == CELESTE_NEON_BGR
    assert tuple(cuadro[10, 11]) == CELESTE_NEON_BGR
    assert tuple(cuadro[10, 12]) == CELESTE_NEON_BGR
    assert not cuadro[10, 13].any()
    assert not cuadro[13, 10].any()


def test_una_cara_localizada_no_se_puede_modificar() -> None:
    cara = _cara((1.0, 2.0))

    with pytest.raises(dataclasses.FrozenInstanceError):
        cara.x = 5.0
