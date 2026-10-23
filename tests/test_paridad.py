"""Paridad entre el modelo entrenado y su ONNX exportado (SPEC/9 §3.6).

El ONNX es un modelo diminuto generado en la prueba (dos nodos Constant, opset 17, ir_version 9)
y corre en ONNX Runtime real; el modelo entrenado es un doble que devuelve tensores conocidos.
"""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper, numpy_helper

from ml.paridad import (
    TOLERANCIA_ABSOLUTA,
    TOLERANCIA_RELATIVA,
    ComparacionDeSalida,
    ParidadInvalidaError,
    comparar_paridad,
    exigir_paridad,
)
from src.inference.adapters.onnx_detector import crear_sesion

pytestmark = pytest.mark.integration

CAJAS = np.array([[[0.5, 0.5, 0.5, 0.25]]], dtype=np.float32)
LOGITS = np.array([[[-10.0, 10.0, 2.0]]], dtype=np.float32)
ENTRADA = np.zeros((1, 3, 4, 8), dtype=np.float32)


def _constante(nombre: str, valores: np.ndarray) -> onnx.NodeProto:
    tensor = numpy_helper.from_array(valores, name=f"{nombre}_valor")
    return helper.make_node("Constant", inputs=[], outputs=[nombre], value=tensor)


def _modelo_diminuto(ruta: Path) -> Path:
    grafo = helper.make_graph(
        [_constante("dets", CAJAS), _constante("labels", LOGITS)],
        "detr_diminuto",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 4, 8])],
        outputs=[
            helper.make_tensor_value_info("dets", TensorProto.FLOAT, [1, 1, 4]),
            helper.make_tensor_value_info("labels", TensorProto.FLOAT, [1, 1, 3]),
        ],
    )
    modelo = helper.make_model(grafo, opset_imports=[helper.make_opsetid("", 17)], ir_version=9)
    onnx.save(modelo, ruta)
    return ruta


class ReferenciaFalsa:
    """Doble del modelo entrenado: devuelve las salidas dadas y anota cada entrada."""

    def __init__(self, *salidas: np.ndarray) -> None:
        self._salidas = list(salidas)
        self.entradas: list[np.ndarray] = []

    def salidas(self, entrada: np.ndarray) -> Sequence[np.ndarray]:
        self.entradas.append(entrada)
        return self._salidas


@pytest.fixture
def sesion(tmp_path: Path) -> object:
    return crear_sesion(str(_modelo_diminuto(tmp_path / "modelo.onnx")))


def test_la_tolerancia_es_la_declarada_antes_de_la_primera_corrida() -> None:
    assert (TOLERANCIA_RELATIVA, TOLERANCIA_ABSOLUTA) == (1e-3, 1e-5)


def test_salidas_identicas_tienen_paridad(sesion: object) -> None:
    referencia = ReferenciaFalsa(CAJAS, LOGITS)
    entradas = [ENTRADA, ENTRADA]

    comparaciones = comparar_paridad(referencia, sesion, entradas)

    assert comparaciones == [
        ComparacionDeSalida(0, "dets", 0.0, True),
        ComparacionDeSalida(0, "labels", 0.0, True),
        ComparacionDeSalida(1, "dets", 0.0, True),
        ComparacionDeSalida(1, "labels", 0.0, True),
    ]
    assert len(referencia.entradas) == len(entradas)


def test_una_diferencia_dentro_de_la_tolerancia_tiene_paridad(sesion: object) -> None:
    # 0.005 es la mitad de lo admitido para el logit de valor 10 (1e-5 + 1e-3 · 10).
    referencia = ReferenciaFalsa(CAJAS, LOGITS + np.array([[[0, 0.005, 0]]], dtype=np.float32))

    [_, logits] = comparar_paridad(referencia, sesion, [ENTRADA])

    assert logits.dentro is True


def test_una_diferencia_fuera_de_la_tolerancia_rompe_la_paridad(sesion: object) -> None:
    referencia = ReferenciaFalsa(CAJAS + np.float32(0.01), LOGITS)

    [cajas, logits] = comparar_paridad(referencia, sesion, [ENTRADA])

    assert (cajas.dentro, logits.dentro) == (False, True)
    assert cajas.diferencia_maxima == pytest.approx(0.01, abs=1e-6)


def test_un_valor_no_finito_rompe_la_paridad(sesion: object) -> None:
    con_nan = LOGITS.copy()
    con_nan[0, 0, 0] = np.nan

    [_, logits] = comparar_paridad(ReferenciaFalsa(CAJAS, con_nan), sesion, [ENTRADA])

    assert logits.dentro is False


def test_la_tolerancia_relativa_se_mide_sobre_la_referencia(sesion: object) -> None:
    # Para el logit 10, |onnx - ref| = 0.0101 > 1e-5 + 1e-3 · 10 = 0.01001.
    referencia = ReferenciaFalsa(CAJAS, LOGITS + np.array([[[0, 0.0101, 0]]], dtype=np.float32))

    [_, logits] = comparar_paridad(referencia, sesion, [ENTRADA])

    assert logits.dentro is False


@pytest.mark.parametrize(
    ("salidas", "mensaje"),
    [
        ((CAJAS,), "Imagen 0: el modelo entrenado devolvió 1 salidas y el ONNX 2."),
        (
            (CAJAS[:, :, :2], LOGITS),
            'Imagen 0, salida "dets": forma (1, 1, 2) en el modelo entrenado y (1, 1, 4) '
            "en el ONNX.",
        ),
    ],
    ids=["cantidad", "forma"],
)
def test_salidas_incomparables_fallan_en_voz_alta(
    sesion: object, salidas: tuple[np.ndarray, ...], mensaje: str
) -> None:
    with pytest.raises(ParidadInvalidaError) as error:
        comparar_paridad(ReferenciaFalsa(*salidas), sesion, [ENTRADA])

    assert str(error.value) == mensaje


def test_sin_imagenes_no_hay_paridad_que_afirmar(sesion: object) -> None:
    with pytest.raises(ParidadInvalidaError) as error:
        comparar_paridad(ReferenciaFalsa(CAJAS, LOGITS), sesion, [])

    assert str(error.value) == "La paridad necesita al menos una imagen fija."


def test_exigir_paridad_lista_cada_salida_fuera_de_tolerancia(sesion: object) -> None:
    referencia = ReferenciaFalsa(CAJAS + np.float32(0.25), LOGITS)

    with pytest.raises(ParidadInvalidaError) as error:
        exigir_paridad(referencia, sesion, [ENTRADA])

    assert str(error.value) == (
        "El ONNX no reproduce al modelo entrenado (tolerancia relativa 0.001, absoluta 1e-05; "
        "no se amplía para que pase, SPEC/9 §3.6):\n"
        'Imagen 0, salida "dets": diferencia máxima 0.25.'
    )


def test_exigir_paridad_no_falla_si_todo_coincide(sesion: object) -> None:
    exigir_paridad(ReferenciaFalsa(CAJAS, LOGITS), sesion, [ENTRADA])
