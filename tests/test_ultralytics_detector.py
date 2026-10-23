"""Adaptador temporal de Ultralytics a DetectorPort (SPEC/9 §1.3.4), con un doble del modelo."""

import logging

import numpy as np
import pytest

from src.inference.adapters.ultralytics_detector import DetectorUltralytics
from src.inference.ports import DetectorPort
from src.inference.types import (
    CATALOGO_COCO,
    Caja,
    ClaseObjeto,
    ConfianzaInvalidaError,
    Deteccion,
)
from tests.dobles_ultralytics import CajasFalsas, DeteccionCruda, ModeloFalso, TensorFalso

ID_PERSONA = 0
ID_AUTO = 2
ID_CELULAR = 67
FRAME = np.zeros((10, 10, 3), dtype=np.uint8)


class _Resultado:
    def __init__(self, cajas: CajasFalsas) -> None:
        self.boxes = cajas


def _detectar(filas: list[DeteccionCruda], confianza_minima: float = 0.0) -> list[Deteccion]:
    detector = DetectorUltralytics(ModeloFalso(filas), CATALOGO_COCO, confianza_minima)

    return detector.detectar(FRAME)


def test_detector_ultralytics_cumple_el_puerto() -> None:
    detector: DetectorPort = DetectorUltralytics(ModeloFalso([]), CATALOGO_COCO, 0.0)

    assert detector.detectar(FRAME) == []


def test_detector_ultralytics_traduce_ids_a_clases_semanticas() -> None:
    detecciones = _detectar(
        [
            DeteccionCruda(ID_PERSONA, (1.0, 2.0, 3.0, 4.0), 0.5),
            DeteccionCruda(ID_CELULAR, (5.0, 6.0, 7.0, 8.0), 0.25),
        ]
    )

    assert detecciones == [
        Deteccion(ClaseObjeto.PERSONA, 0.5, Caja(1.0, 2.0, 3.0, 4.0)),
        Deteccion(ClaseObjeto.CELULAR, 0.25, Caja(5.0, 6.0, 7.0, 8.0)),
    ]


def test_detector_ultralytics_descarta_clases_fuera_del_catalogo() -> None:
    assert _detectar([DeteccionCruda(ID_AUTO, (1.0, 2.0, 3.0, 4.0))]) == []


# Valores exactos en float32 (el tensor del modelo): el borde "igual" no depende del redondeo.
@pytest.mark.parametrize(
    ("confianza", "cantidad"), [(0.25, 0), (0.5, 1), (0.75, 1)], ids=["debajo", "igual", "encima"]
)
def test_detector_ultralytics_filtra_por_confianza_minima(confianza: float, cantidad: int) -> None:
    filas = [DeteccionCruda(ID_PERSONA, (1.0, 2.0, 3.0, 4.0), confianza)]

    assert len(_detectar(filas, confianza_minima=0.5)) == cantidad


def test_detector_ultralytics_descarta_cajas_degeneradas_y_lo_registra(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="src.inference.adapters.ultralytics_detector")

    detecciones = _detectar([DeteccionCruda(ID_PERSONA, (3.0, 2.0, 3.0, 4.0))])

    assert detecciones == []
    assert caplog.messages == [
        "Caja degenerada descartada: Caja degenerada (3.0, 2.0, 3.0, 4.0): "
        "se necesita x2 > x1 y y2 > y1."
    ]


def test_detector_ultralytics_con_salidas_de_distinto_largo_falla_ruidosamente() -> None:
    modelo = ModeloFalso([DeteccionCruda(ID_PERSONA, (1.0, 2.0, 3.0, 4.0))])
    cajas = modelo(FRAME)[0].boxes
    cajas.conf = TensorFalso([0.9, 0.8])
    detector = DetectorUltralytics(
        lambda _frame, **_opciones: [_Resultado(cajas)], CATALOGO_COCO, 0
    )

    with pytest.raises(ValueError, match="zip"):
        detector.detectar(FRAME)


def test_detector_ultralytics_pide_inferencia_silenciosa_del_frame() -> None:
    modelo = ModeloFalso([])
    detector = DetectorUltralytics(modelo, CATALOGO_COCO, 0.0)

    detector.detectar(FRAME)

    assert modelo.frames_recibidos == [FRAME]
    assert modelo.opciones_recibidas == [{"verbose": False}]


@pytest.mark.parametrize("confianza_minima", [-0.1, 1.1])
def test_detector_ultralytics_rechaza_una_confianza_minima_invalida(
    confianza_minima: float,
) -> None:
    with pytest.raises(ConfianzaInvalidaError):
        DetectorUltralytics(ModeloFalso([]), CATALOGO_COCO, confianza_minima)
