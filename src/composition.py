"""Raíz de composición única (SPEC/9 §1.3.6 y §1.7).

La GUI (`main_ui.py`), el modo headless (`main.py`) y el benchmark crean el detector con esta
función: la lección de CR-04 es no volver a tener dos caminos que divergen. El motor se elige
con `config.DETECTION_ENGINE`; el interruptor existe solo durante la migración y se elimina al
contraer (A-16, decisión D8).
"""

import json
from collections.abc import Mapping
from pathlib import Path, PurePath
from typing import Any

from config import config
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
        return DetectorUltralytics(_cargar_yolo(ruta_modelo), CATALOGO_COCO, confianza_minima)
    if motor == MOTOR_ONNX:
        configuracion = _configuracion_onnx(ruta_modelo, confianza_minima, manifiesto or {})
        return DetectorOnnx(crear_sesion(ruta_modelo), configuracion)
    raise MotorDesconocidoError(f"Motor desconocido: {motor} (usa ultralytics u onnx).")


def crear_detector_configurado(confianza_minima: float) -> DetectorPort:
    """Detector de la app: motor, modelo y manifiesto salen de `config/config.py`."""
    motor = config.DETECTION_ENGINE
    manifiesto = _leer_manifiesto(config.MANIFEST_PATH) if motor == MOTOR_ONNX else None
    return crear_detector(config.MODEL_PATH, confianza_minima, motor, manifiesto)


def _leer_manifiesto(ruta: str) -> dict[str, Any]:
    contenido: dict[str, Any] = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return contenido


def _cargar_yolo(ruta_modelo: str) -> Any:
    """Carga los pesos .pt con el parche de CR-05, confinado al motor heredado.

    ultralytics 8.1 deserializa con pickle completo y torch >= 2.6 lo rechaza por omisión.
    Imports diferidos: el camino ONNX no carga torch ni ultralytics. Todo esto se elimina al
    contraer (A-16, D8); AC-005 queda pendiente hasta entonces.
    """
    import torch
    from ultralytics import YOLO

    original = torch.load

    def _load_sin_weights_only(*argumentos: Any, **opciones: Any) -> Any:
        opciones["weights_only"] = False
        return original(*argumentos, **opciones)

    torch.load = _load_sin_weights_only
    try:
        return YOLO(ruta_modelo)
    finally:
        # CR-05: se restaura en todos los caminos para no dejar pickle inseguro en la sesión.
        torch.load = original


def _declara(entrada: Mapping[str, Any], ruta: str) -> bool:
    """La ruta del modelo termina en el `archivo` (relativo) de la entrada del manifiesto."""
    declarada = PurePath(entrada["archivo"]).parts
    return PurePath(ruta).parts[-len(declarada) :] == declarada


def _configuracion_onnx(
    ruta: str, confianza_minima: float, manifiesto: Mapping[str, Any]
) -> ConfiguracionOnnx:
    entrada = next((m for m in manifiesto.get("modelos", []) if _declara(m, ruta)), None)
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
