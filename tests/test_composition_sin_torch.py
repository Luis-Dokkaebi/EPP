"""Regresión de SPEC/9 §1.9: el camino ONNX de la raíz de composición no carga torch.

Se corre en un intérprete aparte porque en la suite otras pruebas ya importaron torch.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.modelos_onnx import ID_PERSONA, modelo_diminuto
from tests.utilidades_scripts import RAIZ

pytestmark = pytest.mark.integration

PROGRAMA = """
import json, sys
from src.composition import MOTOR_ONNX, crear_detector
detector = crear_detector(sys.argv[1], 0.5, MOTOR_ONNX, json.loads(sys.argv[2]))
print(type(detector).__name__, sorted({"torch", "ultralytics"} & set(sys.modules)))
"""


def test_el_motor_onnx_no_importa_torch_ni_ultralytics(tmp_path: Path) -> None:
    modelo = modelo_diminuto(tmp_path / "modelo.onnx")
    entrada = {"archivo": "modelo.onnx", "clases": {str(ID_PERSONA): "persona"},
               "media": [0.5] * 3, "desviacion": [0.25] * 3}  # fmt: skip

    # S603: el intérprete de la suite con un programa fijo.
    resultado = subprocess.run(
        [sys.executable, "-c", PROGRAMA, str(modelo), json.dumps({"modelos": [entrada]})],  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == "DetectorOnnx []"
