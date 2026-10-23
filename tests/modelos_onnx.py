"""Modelo ONNX diminuto (dos nodos Constant): las pruebas no cargan pesos reales de varios MB."""

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

ID_PERSONA = 1
NUMERO_DE_CLASES = 91
OPSET = 17
IR_VERSION = 9  # la que acepta onnxruntime 1.31 para el opset 17 (onnx 1.23 escribe la 14)


def _constante(nombre: str, valores: np.ndarray) -> onnx.NodeProto:
    tensor = numpy_helper.from_array(valores.astype(np.float32), name=f"{nombre}_valor")
    return helper.make_node("Constant", inputs=[], outputs=[nombre], value=tensor)


def modelo_diminuto(ruta: Path) -> Path:
    cajas = np.array([[[0.5, 0.5, 0.5, 0.25]]])
    logits = np.full((1, 1, NUMERO_DE_CLASES), -10.0)
    logits[0, 0, ID_PERSONA] = 10.0
    grafo = helper.make_graph(
        [_constante("dets", cajas), _constante("labels", logits)],
        "detr_diminuto",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 4, 8])],
        outputs=[
            helper.make_tensor_value_info("dets", TensorProto.FLOAT, [1, 1, 4]),
            helper.make_tensor_value_info("labels", TensorProto.FLOAT, [1, 1, NUMERO_DE_CLASES]),
        ],
    )
    modelo = helper.make_model(
        grafo, opset_imports=[helper.make_opsetid("", OPSET)], ir_version=IR_VERSION
    )
    onnx.save(modelo, ruta)
    return ruta
