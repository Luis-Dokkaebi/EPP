"""Conversión de Deteccion al formato de ByteTrack (SPEC/9 §1.3.5)."""

import numpy as np

from src.inference.types import Caja, ClaseObjeto, Deteccion
from src.tracking.person_tracker import separar_personas_y_celulares

ORDINAL_PERSONA = 0


def test_separar_sin_detecciones_devuelve_personas_vacias_y_ningun_celular() -> None:
    personas, celulares = separar_personas_y_celulares([])

    assert personas.xyxy.shape == (0, 4)
    assert len(personas) == 0
    assert celulares == []


def test_separar_entrega_personas_a_bytetrack_y_celulares_como_enteros() -> None:
    detecciones = [
        Deteccion(ClaseObjeto.CELULAR, 0.3, Caja(5.7, 6.2, 30.9, 40.1)),
        Deteccion(ClaseObjeto.PERSONA, 0.9, Caja(10.0, 20.0, 110.0, 220.0)),
        Deteccion(ClaseObjeto.PERSONA, 0.6, Caja(1.5, 2.5, 3.5, 4.5)),
    ]

    personas, celulares = separar_personas_y_celulares(detecciones)

    assert personas.xyxy.tolist() == [[10.0, 20.0, 110.0, 220.0], [1.5, 2.5, 3.5, 4.5]]
    assert personas.confidence.tolist() == [np.float32(0.9), np.float32(0.6)]
    assert personas.class_id.tolist() == [ORDINAL_PERSONA, ORDINAL_PERSONA]
    assert personas.xyxy.dtype == np.float32
    assert celulares == [(5, 6, 30, 40)]
