"""Contrato de entrada y salida con ONNX Runtime real y un modelo diminuto (SPEC/9 §1.4).

El modelo se genera en la prueba (dos nodos Constant): no hay pesos reales de varios MB.
"""

from pathlib import Path

import numpy as np
import pytest

from src.inference.adapters.onnx_detector import (
    PROVEEDOR_CPU,
    ConfiguracionOnnx,
    DetectorOnnx,
    crear_sesion,
)
from src.inference.types import Caja, CatalogoDeClases, ClaseObjeto
from tests.modelos_onnx import ID_PERSONA, modelo_diminuto

pytestmark = pytest.mark.integration


def test_crear_sesion_carga_el_modelo_con_el_proveedor_de_cpu(tmp_path: Path) -> None:
    sesion = crear_sesion(str(modelo_diminuto(tmp_path / "modelo.onnx")))

    assert sesion.get_providers() == [PROVEEDOR_CPU]


def test_detector_onnx_con_runtime_real_respeta_el_contrato(tmp_path: Path) -> None:
    sesion = crear_sesion(str(modelo_diminuto(tmp_path / "modelo.onnx")))
    configuracion = ConfiguracionOnnx(
        media=(0.485, 0.456, 0.406),
        desviacion=(0.229, 0.224, 0.225),
        catalogo=CatalogoDeClases({ID_PERSONA: ClaseObjeto.PERSONA}),
        confianza_minima=0.5,
    )

    [deteccion] = DetectorOnnx(sesion, configuracion).detectar(np.zeros((100, 200, 3), np.uint8))

    assert deteccion.clase is ClaseObjeto.PERSONA
    assert deteccion.caja == Caja(50.0, 37.5, 150.0, 62.5)
