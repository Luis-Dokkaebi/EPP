"""Raíz de composición única (SPEC/9 §1.3.6 y §1.7).

La GUI (`main_ui.py`), el modo headless (`main.py`) y el benchmark crean el detector con esta
función: la lección de CR-04 es no volver a tener dos caminos que divergen. El motor es ONNX
Runtime (MIT) con RF-DETR (Apache-2.0); Ultralytics (AGPL) salió del producto (ADR-001, A-16).
"""

import json
from collections.abc import Mapping
from pathlib import Path, PurePath
from typing import Any

from config import config
from src.inference.adapters.onnx_detector import ConfiguracionOnnx, DetectorOnnx, crear_sesion
from src.inference.ports import DetectorPort
from src.inference.types import CatalogoDeClases, ClaseObjeto
from src.models.model_verifier import assert_model_integrity
from src.recognition.motor_facial_opencv import MotorFacialOpenCV, crear_motor_facial_opencv


class ModeloNoDeclaradoError(ValueError):
    """El modelo ONNX no figura en models/manifest.json con sus clases y su normalización."""


def crear_detector(
    ruta_modelo: str, confianza_minima: float, manifiesto: Mapping[str, Any]
) -> DetectorPort:
    """Detector ONNX del modelo de `ruta_modelo`, con las clases y la normalización declaradas."""
    configuracion = _configuracion_onnx(ruta_modelo, confianza_minima, manifiesto)
    return DetectorOnnx(crear_sesion(ruta_modelo), configuracion)


def crear_detector_configurado(confianza_minima: float) -> DetectorPort:
    """Detector de la app: modelo y manifiesto salen de `config/config.py`."""
    manifiesto = leer_manifiesto(config.MANIFEST_PATH)
    return crear_detector(config.MODEL_PATH, confianza_minima, manifiesto)


def crear_motor_facial_configurado() -> MotorFacialOpenCV:
    """YuNet + SFace de `config/config.py`, solo si sus hashes son los del manifiesto."""
    for ruta in (config.FACE_DETECTOR_PATH, config.FACE_RECOGNIZER_PATH):
        assert_model_integrity(ruta)
    return crear_motor_facial_opencv(config.FACE_DETECTOR_PATH, config.FACE_RECOGNIZER_PATH)


def leer_manifiesto(ruta: str) -> dict[str, Any]:
    contenido: dict[str, Any] = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return contenido


def _declara(entrada: Mapping[str, Any], ruta: str) -> bool:
    """La ruta del modelo termina en el `archivo` (relativo) de la entrada del manifiesto."""
    declarada = PurePath(entrada["archivo"]).parts
    return PurePath(ruta).parts[-len(declarada) :] == declarada


def entrada_del_modelo(ruta: str, manifiesto: Mapping[str, Any]) -> Mapping[str, Any]:
    """La entrada de models/manifest.json que declara el modelo de `ruta`."""
    entrada = next((m for m in manifiesto.get("modelos", []) if _declara(m, ruta)), None)
    if entrada is None:
        raise ModeloNoDeclaradoError(
            f"{ruta} no está declarado en models/manifest.json (clases y normalización)."
        )
    return entrada


def clases_declaradas(entrada: Mapping[str, Any]) -> frozenset[ClaseObjeto]:
    """Las clases que el manifiesto dice que detecta el modelo."""
    return frozenset(ClaseObjeto(nombre) for nombre in entrada["clases"].values())


def _configuracion_onnx(
    ruta: str, confianza_minima: float, manifiesto: Mapping[str, Any]
) -> ConfiguracionOnnx:
    entrada = entrada_del_modelo(ruta, manifiesto)
    clases = {int(id_): ClaseObjeto(nombre) for id_, nombre in entrada["clases"].items()}
    return ConfiguracionOnnx(
        media=tuple(entrada["media"]),
        desviacion=tuple(entrada["desviacion"]),
        catalogo=CatalogoDeClases(clases),
        confianza_minima=confianza_minima,
    )
