"""Anotador propio de frames (SPEC/9 §1.3.5): reemplaza a `results[0].plot()` de Ultralytics."""

import hashlib

import numpy as np

from src.inference.types import Caja, ClaseObjeto, Deteccion
from src.tracking.annotator import COLORES, AnotadorDeFrames

NEGRO = [0, 0, 0]
VERDE = [0, 255, 0]
ROJO = [0, 0, 255]
# sha256 del frame anotado de _escena() con opencv-python-headless 4.9.0.80 (fijado): fija color,
# grosor, fuente, escala, texto y posición de la etiqueta. Si cambia el dibujo a propósito,
# revisa la imagen y actualiza el valor.
# pragma: allowlist nextline secret
HUELLA_ESCENA = "cf82e203962d2bad7558b0315937d5cac75f0af94343588db17c2e0905f8b4e1"


def _frame() -> np.ndarray:
    return np.zeros((100, 200, 3), dtype=np.uint8)


def test_anotador_sin_detecciones_devuelve_una_copia_identica() -> None:
    frame = _frame()

    anotado = AnotadorDeFrames().anotar(frame, [])

    assert anotado is not frame
    assert np.array_equal(anotado, frame)


def _escena() -> list[Deteccion]:
    return [
        Deteccion(ClaseObjeto.PERSONA, 0.87, Caja(20.4, 30.6, 120.0, 90.0)),
        Deteccion(ClaseObjeto.CELULAR, 0.5, Caja(150.0, 40.0, 190.0, 80.0)),
    ]


def test_anotador_dibuja_la_caja_con_el_color_de_su_clase_sin_tocar_el_original() -> None:
    frame = _frame()

    anotado = AnotadorDeFrames().anotar(frame, _escena())

    assert anotado[60, 20].tolist() == VERDE
    assert anotado[60, 120].tolist() == VERDE
    assert anotado[60, 150].tolist() == ROJO
    assert anotado[60, 70].tolist() == NEGRO
    assert frame.max() == 0


def test_anotador_dibuja_bordes_de_tres_pixeles_centrados_en_la_coordenada() -> None:
    anotado = AnotadorDeFrames().anotar(_frame(), _escena())

    assert anotado[60, 16:25, 1].tolist() == [0, 0, 0, 255, 255, 255, 0, 0, 0]


def test_anotador_produce_exactamente_la_imagen_de_referencia() -> None:
    anotado = AnotadorDeFrames().anotar(_frame(), _escena())

    assert hashlib.sha256(anotado.tobytes()).hexdigest() == HUELLA_ESCENA


def test_anotador_escribe_la_clase_y_la_confianza_sobre_la_caja() -> None:
    persona = Deteccion(ClaseObjeto.PERSONA, 0.87, Caja(20.0, 40.0, 120.0, 90.0))

    anotado = AnotadorDeFrames().anotar(_frame(), [persona])

    assert anotado[25:39, 20:120].any()
    assert not anotado[0:20, :].any()


def test_anotador_usa_verde_para_personas_y_rojo_para_celulares() -> None:
    assert COLORES == {ClaseObjeto.PERSONA: (0, 255, 0), ClaseObjeto.CELULAR: (0, 0, 255)}
