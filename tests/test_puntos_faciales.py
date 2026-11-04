"""Modo demostración: dibuja los 5 puntos de referencia de cada cara sobre el cuadro."""

import numpy as np

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
