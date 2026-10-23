"""Raíz de composición única (SPEC/9 §1.3.6 y §1.7).

La GUI (`main_ui.py`), el modo headless (`main.py`) y el benchmark crean el detector con esta
función: la lección de CR-04 es no volver a tener dos caminos que divergen. El motor se elige
con `config.DETECTION_ENGINE`; el interruptor existe solo durante la migración y se elimina al
contraer (A-16, decisión D8).
"""

from collections.abc import Mapping
from typing import Any

from src.inference.adapters.onnx_detector import ConfiguracionOnnx, DetectorOnnx, crear_sesion
from src.inference.adapters.ultralytics_detector import DetectorUltralytics
from src.inference.ports import DetectorPort
from src.inference.types import CATALOGO_COCO, CatalogoDeClases, ClaseObjeto

MOTOR_ULTRALYTICS = "ultralytics"
MOTOR_ONNX = "onnx"


class MotorDesconocidoError(ValueError):
    """config.DETECTION_ENGINE no nombra un motor soportado."""


class ModeloNoDeclaradoError(ValueError):
    """El modelo ONNX no figura en models/manifest.json con sus clases y su normalización."""


def crear_detector(
    ruta_modelo: str,
    confianza_minima: float,
    motor: str = MOTOR_ULTRALYTICS,
    manifiesto: Mapping[str, Any] | None = None,
) -> DetectorPort:
    """Detector del motor pedido; el manifiesto solo hace falta para ONNX."""
    if motor == MOTOR_ULTRALYTICS:
        # Import diferido: el motor AGPL solo se carga si se elige, y se elimina en A-16 (D8).
        from ultralytics import YOLO

        return DetectorUltralytics(YOLO(ruta_modelo), CATALOGO_COCO, confianza_minima)
    if motor == MOTOR_ONNX:
        configuracion = _configuracion_onnx(ruta_modelo, confianza_minima, manifiesto or {})
        return DetectorOnnx(crear_sesion(ruta_modelo), configuracion)
    raise MotorDesconocidoError(f"Motor desconocido: {motor} (usa ultralytics u onnx).")


def _configuracion_onnx(
    ruta: str, confianza_minima: float, manifiesto: Mapping[str, Any]
) -> ConfiguracionOnnx:
    entrada = next((m for m in manifiesto.get("modelos", []) if m["archivo"] == ruta), None)
    if entrada is None:
        raise ModeloNoDeclaradoError(
            f"{ruta} no está declarado en models/manifest.json (clases y normalización)."
        )
    clases = {int(id_): ClaseObjeto(nombre) for id_, nombre in entrada["clases"].items()}
    return ConfiguracionOnnx(
        media=tuple(entrada["media"]),
        desviacion=tuple(entrada["desviacion"]),
        catalogo=CatalogoDeClases(clases),
        confianza_minima=confianza_minima,
    )
