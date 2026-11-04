"""Dibujo de los puntos de referencia faciales del modo demostración de la GUI."""

from collections.abc import Iterable

import cv2
import numpy as np

from src.recognition.ports import CaraLocalizada

COLOR_DE_PUNTO = (255, 200, 50)
RADIO_DE_PUNTO = 2
RELLENO = -1


def dibujar_puntos_faciales(cuadro: np.ndarray, caras: Iterable[CaraLocalizada]) -> None:
    """Pinta sobre `cuadro` (BGR, en el lugar) cada punto de cada cara."""
    for cara in caras:
        for x, y in cara.puntos:
            cv2.circle(cuadro, (round(x), round(y)), RADIO_DE_PUNTO, COLOR_DE_PUNTO, RELLENO)
