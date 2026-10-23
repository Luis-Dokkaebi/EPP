"""Raíz de composición única (SPEC/9 §1.3.6): GUI y headless crean el detector del mismo modo."""

import sys
import types

import numpy as np
import pytest

from src import composition as composicion
from src.composition import (
    MOTOR_ONNX,
    MOTOR_ULTRALYTICS,
    ModeloNoDeclaradoError,
    MotorDesconocidoError,
    crear_detector,
)
from src.inference.adapters.onnx_detector import DetectorOnnx
from src.inference.adapters.ultralytics_detector import DetectorUltralytics
from src.inference.types import Caja, ClaseObjeto, Deteccion
from tests.dobles_ultralytics import DeteccionCruda, ModeloFalso

ID_PERSONA = 0


@pytest.fixture
def modelos_cargados(monkeypatch: pytest.MonkeyPatch) -> dict[str, ModeloFalso]:
    """Reemplaza el paquete `ultralytics`: la prueba no carga pesos reales (CLAUDE.md §16)."""
    cargados: dict[str, ModeloFalso] = {}

    def yolo(ruta: str) -> ModeloFalso:
        cargados[ruta] = ModeloFalso([DeteccionCruda(ID_PERSONA, (1.0, 2.0, 3.0, 4.0), 0.5)])
        return cargados[ruta]

    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=yolo))
    return cargados


def test_crear_detector_carga_el_modelo_de_la_ruta_indicada(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    crear_detector("modelos/personas.pt", confianza_minima=0.0)

    assert list(modelos_cargados) == ["modelos/personas.pt"]


def test_crear_detector_devuelve_un_puerto_con_clases_semanticas(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    detector = crear_detector("m.pt", confianza_minima=0.0)

    detecciones = detector.detectar(np.zeros((4, 4, 3), dtype=np.uint8))

    assert detecciones == [Deteccion(ClaseObjeto.PERSONA, 0.5, Caja(1.0, 2.0, 3.0, 4.0))]


def test_crear_detector_aplica_la_confianza_minima(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    detector = crear_detector("m.pt", confianza_minima=0.6)

    assert detector.detectar(np.zeros((4, 4, 3), dtype=np.uint8)) == []


def _manifiesto_onnx(ruta: str) -> dict[str, list[dict[str, object]]]:
    return {
        "modelos": [
            {
                "archivo": ruta,
                "clases": {"1": "persona"},
                "media": [0.5] * 3,
                "desviacion": [0.25] * 3,
            }
        ]
    }


def test_crear_detector_con_motor_ultralytics_es_el_adaptador_de_ultralytics(
    modelos_cargados: dict[str, ModeloFalso],
) -> None:
    detector = crear_detector("m.pt", 0.0, motor=MOTOR_ULTRALYTICS, manifiesto={})

    assert isinstance(detector, DetectorUltralytics)


def test_crear_detector_con_motor_onnx_usa_clases_y_normalizacion_del_manifiesto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entrada = types.SimpleNamespace(name="x", shape=(1, 3, 4, 4))
    monkeypatch.setattr(
        composicion,
        "crear_sesion",
        lambda _ruta: types.SimpleNamespace(get_inputs=lambda: [entrada]),
    )

    detector = crear_detector(
        "m.onnx", 0.5, motor=MOTOR_ONNX, manifiesto=_manifiesto_onnx("m.onnx")
    )

    assert isinstance(detector, DetectorOnnx)


@pytest.mark.parametrize(
    ("motor", "manifiesto", "error", "mensaje"),
    [("tensorflow", {}, MotorDesconocidoError,
      "Motor desconocido: tensorflow (usa ultralytics u onnx)."),
     (MOTOR_ONNX, {"modelos": []}, ModeloNoDeclaradoError,
      "m.onnx no está declarado en models/manifest.json (clases y normalización).")],
    ids=["motor-desconocido", "onnx-sin-declarar"],
)  # fmt: skip
def test_crear_detector_falla_ruidosamente_con_un_error_tipado(
    motor: str, manifiesto: dict, error: type[Exception], mensaje: str
) -> None:
    with pytest.raises(error) as excepcion:
        crear_detector("m.onnx", 0.5, motor=motor, manifiesto=manifiesto)

    assert str(excepcion.value) == mensaje


def test_los_nombres_de_motor_son_los_que_admite_la_configuracion() -> None:
    """config.DETECTION_ENGINE usa estos textos literales: cambiarlos rompe la configuración."""
    assert (MOTOR_ULTRALYTICS, MOTOR_ONNX) == ("ultralytics", "onnx")
