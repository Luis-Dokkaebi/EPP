"""Anotador propio de frames (SPEC/9 §1.3.5): reemplaza a `results[0].plot()` de Ultralytics."""

import numpy as np

from src.inference.types import Caja, ClaseObjeto, Deteccion
from src.tracking.annotator import COLORES, AnotadorDeFrames

NEGRO = [0, 0, 0]


def _frame() -> np.ndarray:
    return np.zeros((100, 200, 3), dtype=np.uint8)


def test_anotador_sin_detecciones_devuelve_una_copia_identica() -> None:
    frame = _frame()

    anotado = AnotadorDeFrames().anotar(frame, [])

    assert anotado is not frame
    assert np.array_equal(anotado, frame)


def test_anotador_dibuja_la_caja_con_el_color_de_su_clase_sin_tocar_el_original() -> None:
    frame = _frame()
    persona = Deteccion(ClaseObjeto.PERSONA, 0.87, Caja(20.4, 30.6, 120.0, 90.0))
    celular = Deteccion(ClaseObjeto.CELULAR, 0.5, Caja(150.0, 40.0, 190.0, 80.0))

    anotado = AnotadorDeFrames().anotar(frame, [persona, celular])

    assert anotado[60, 20].tolist() == list(COLORES[ClaseObjeto.PERSONA])
    assert anotado[60, 120].tolist() == list(COLORES[ClaseObjeto.PERSONA])
    assert anotado[60, 150].tolist() == list(COLORES[ClaseObjeto.CELULAR])
    assert anotado[60, 70].tolist() == NEGRO
    assert frame.max() == 0


def test_anotador_escribe_la_clase_y_la_confianza_sobre_la_caja() -> None:
    persona = Deteccion(ClaseObjeto.PERSONA, 0.87, Caja(20.0, 40.0, 120.0, 90.0))

    anotado = AnotadorDeFrames().anotar(_frame(), [persona])

    assert anotado[25:39, 20:120].any()
    assert not anotado[0:20, :].any()


def test_anotador_tiene_un_color_para_cada_clase() -> None:
    assert set(COLORES) == set(ClaseObjeto)
