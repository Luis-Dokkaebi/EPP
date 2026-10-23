"""Adaptador de ONNX Runtime a DetectorPort (SPEC/9 §1.4), con un doble de InferenceSession."""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from src.inference.adapters.onnx_detector import ConfiguracionOnnx, DetectorOnnx
from src.inference.ports import DetectorPort
from src.inference.types import (
    Caja,
    CatalogoDeClases,
    ClaseObjeto,
    ConfianzaInvalidaError,
    Deteccion,
)

ID_PERSONA = 1
ID_CELULAR = 77
NUMERO_DE_CLASES = 91
ANCHO_FRAME, ALTO_FRAME = 200, 100
# Las cajas usan fracciones exactas en float32 (0.25, 0.0625...) para comparar sin redondeo.
LOGIT_SEGURO = 10.0  # sigmoide ~ 0.99995
LOGIT_NULO = -10.0
CATALOGO = CatalogoDeClases({ID_PERSONA: ClaseObjeto.PERSONA, ID_CELULAR: ClaseObjeto.CELULAR})


@dataclass(frozen=True)
class Entrada:
    name: str
    shape: tuple[int, ...]


@dataclass
class SesionFalsa:
    """Doble de onnxruntime.InferenceSession: devuelve cajas y logits fijos (formato DETR)."""

    cajas: list[list[float]]
    logits: list[list[float]]
    recibidos: list[dict[str, np.ndarray]] = field(default_factory=list)

    def get_inputs(self) -> list[Entrada]:
        return [Entrada("input", (1, 3, 4, 8))]

    def run(self, salidas: Any, entradas: dict[str, np.ndarray]) -> list[np.ndarray]:
        self.recibidos.append(entradas)
        return [
            np.asarray([self.cajas], dtype=np.float32).reshape(1, -1, 4),
            np.asarray([self.logits], dtype=np.float32).reshape(1, -1, NUMERO_DE_CLASES),
        ]


def _logits(id_clase: int, valor: float = LOGIT_SEGURO) -> list[float]:
    fila = [LOGIT_NULO] * NUMERO_DE_CLASES
    fila[id_clase] = valor
    return fila


def _configuracion(confianza_minima: float = 0.5) -> ConfiguracionOnnx:
    return ConfiguracionOnnx(
        media=(0.5, 0.5, 0.5),
        desviacion=(0.25, 0.25, 0.25),
        catalogo=CATALOGO,
        confianza_minima=confianza_minima,
    )


def _frame() -> np.ndarray:
    frame = np.zeros((ALTO_FRAME, ANCHO_FRAME, 3), dtype=np.uint8)
    frame[:, :, 0] = 255  # azul en BGR
    return frame


def _detectar(sesion: SesionFalsa, confianza_minima: float = 0.5) -> list[Deteccion]:
    detector: DetectorPort = DetectorOnnx(sesion, _configuracion(confianza_minima))
    return detector.detectar(_frame())


def test_detector_onnx_preprocesa_a_nchw_rgb_normalizado_del_tamano_de_entrada() -> None:
    sesion = SesionFalsa(cajas=[], logits=[])

    _detectar(sesion)

    [entradas] = sesion.recibidos
    tensor = entradas["input"]
    assert tensor.shape == (1, 3, 4, 8)
    assert tensor.dtype == np.float32
    assert tensor[0, 0].tolist() == [[-2.0] * 8] * 4  # rojo 0 -> (0 - 0.5) / 0.25
    assert tensor[0, 2].tolist() == [[2.0] * 8] * 4  # azul 255 -> (1 - 0.5) / 0.25


def test_detector_onnx_reescala_cajas_cxcywh_normalizadas_al_frame() -> None:
    sesion = SesionFalsa(cajas=[[0.5, 0.5, 0.5, 0.25]], logits=[_logits(ID_PERSONA)])

    [deteccion] = _detectar(sesion)

    assert deteccion.clase is ClaseObjeto.PERSONA
    assert deteccion.caja == Caja(50.0, 37.5, 150.0, 62.5)
    assert deteccion.confianza == pytest.approx(0.9999546, abs=1e-6)


def test_detector_onnx_traduce_cada_clase_con_el_catalogo_del_modelo() -> None:
    sesion = SesionFalsa(
        cajas=[[0.5, 0.5, 0.5, 0.2], [0.25, 0.25, 0.1, 0.1], [0.75, 0.75, 0.1, 0.1]],
        logits=[_logits(ID_CELULAR), _logits(ID_PERSONA), _logits(3)],
    )

    detecciones = _detectar(sesion)

    assert [deteccion.clase for deteccion in detecciones] == [
        ClaseObjeto.CELULAR,
        ClaseObjeto.PERSONA,
    ]


@pytest.mark.parametrize(
    ("logit", "cantidad"), [(-0.1, 0), (0.0, 1), (0.1, 1)], ids=["debajo", "igual", "encima"]
)
def test_detector_onnx_filtra_por_confianza_minima(logit: float, cantidad: int) -> None:
    sesion = SesionFalsa(cajas=[[0.5, 0.5, 0.5, 0.2]], logits=[_logits(ID_PERSONA, logit)])

    assert len(_detectar(sesion, confianza_minima=0.5)) == cantidad


def test_detector_onnx_usa_la_clase_mas_probable_de_cada_consulta() -> None:
    logits = _logits(ID_PERSONA, 1.0)
    logits[ID_CELULAR] = 2.0
    sesion = SesionFalsa(cajas=[[0.5, 0.5, 0.5, 0.2]], logits=[logits])

    [deteccion] = _detectar(sesion)

    assert deteccion.clase is ClaseObjeto.CELULAR


def test_detector_onnx_recorta_las_cajas_al_borde_del_frame() -> None:
    sesion = SesionFalsa(cajas=[[0.0625, 0.9375, 0.25, 0.25]], logits=[_logits(ID_PERSONA)])

    [deteccion] = _detectar(sesion)

    assert deteccion.caja == Caja(0.0, 81.25, 37.5, 100.0)


def test_detector_onnx_recorta_las_cajas_al_borde_superior() -> None:
    sesion = SesionFalsa(cajas=[[0.5, 0.0625, 0.25, 0.25]], logits=[_logits(ID_PERSONA)])

    [deteccion] = _detectar(sesion)

    assert deteccion.caja == Caja(75.0, 0.0, 125.0, 18.75)


@pytest.mark.parametrize(
    "caja",
    [
        [0.5, 0.5, 0.0, 0.2],
        [0.5, 0.5, 0.2, 0.0],
        [1.5, 0.5, 0.2, 0.2],
        [-0.5, 0.5, 0.25, 0.25],
        [0.5, -0.5, 0.25, 0.25],
    ],
    ids=["ancho-cero", "alto-cero", "fuera-por-la-derecha", "fuera-por-la-izquierda", "arriba"],
)
def test_detector_onnx_descarta_cajas_degeneradas(caja: list[float]) -> None:
    sesion = SesionFalsa(cajas=[caja], logits=[_logits(ID_PERSONA)])

    assert _detectar(sesion) == []


def test_detector_onnx_registra_la_caja_degenerada_descartada(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="src.inference.adapters.onnx_detector")
    sesion = SesionFalsa(cajas=[[0.5, 0.5, 0.0, 0.25]], logits=[_logits(ID_PERSONA)])

    _detectar(sesion)

    assert caplog.messages == [
        "Caja degenerada descartada: Caja degenerada (100.0, 37.5, 100.0, 62.5): "
        "se necesita x2 > x1 y y2 > y1."
    ]


def test_detector_onnx_con_salidas_de_distinto_largo_falla_ruidosamente() -> None:
    sesion = SesionFalsa(cajas=[[0.5, 0.5, 0.25, 0.25]] * 2, logits=[_logits(ID_PERSONA)])

    with pytest.raises(ValueError, match="zip"):
        _detectar(sesion)


def test_configuracion_onnx_es_inmutable() -> None:
    configuracion = _configuracion()

    with pytest.raises(AttributeError):
        configuracion.confianza_minima = 0.9  # type: ignore[misc]  # se verifica que no se pueda


def test_detector_onnx_sin_consultas_devuelve_vacio() -> None:
    assert _detectar(SesionFalsa(cajas=[], logits=[])) == []


@pytest.mark.parametrize("confianza_minima", [-0.1, 1.1])
def test_configuracion_onnx_rechaza_una_confianza_minima_invalida(confianza_minima: float) -> None:
    with pytest.raises(ConfianzaInvalidaError):
        _configuracion(confianza_minima)
