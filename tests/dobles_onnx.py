"""Doble de una sesión de ONNX Runtime con la salida de RF-DETR: las pruebas no cargan pesos.

Cada detección se da en píxeles de un cuadro de `ancho` x `alto`; la sesión la devuelve como
la daría el modelo (caja cx, cy, w, h normalizada y un logit por clase de COCO-91).
"""

import math
import types
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.inference.adapters.onnx_detector import ConfiguracionOnnx, DetectorOnnx
from src.inference.types import CatalogoDeClases, ClaseObjeto, Deteccion

ID_PERSONA = 1
ID_CELULAR = 77
NUMERO_DE_CLASES = 91
LOGIT_AUSENTE = -20.0
LADO_DE_ENTRADA = 384


@dataclass(frozen=True)
class DeteccionCruda:
    """Clase del modelo (COCO-91), caja xyxy en píxeles y confianza."""

    clase: int
    caja: tuple[float, float, float, float]
    confianza: float = 0.9


def _logit(probabilidad: float) -> float:
    return math.log(probabilidad / (1.0 - probabilidad))


class SesionOnnxFalsa:
    def __init__(self, detecciones: Sequence[DeteccionCruda], ancho: int, alto: int) -> None:
        self._detecciones = detecciones
        self._ancho, self._alto = ancho, alto
        self.entradas_recibidas: list[np.ndarray] = []

    def get_inputs(self) -> list[Any]:
        forma = (1, 3, LADO_DE_ENTRADA, LADO_DE_ENTRADA)
        return [types.SimpleNamespace(name="input", shape=forma)]

    def run(self, _salidas: Any, entradas: dict[str, np.ndarray]) -> list[np.ndarray]:
        self.entradas_recibidas.append(entradas["input"])
        cajas = np.zeros((1, len(self._detecciones), 4), dtype=np.float32)
        logits = np.full((1, len(self._detecciones), NUMERO_DE_CLASES), LOGIT_AUSENTE)
        for indice, deteccion in enumerate(self._detecciones):
            x1, y1, x2, y2 = deteccion.caja
            cajas[0, indice] = (
                (x1 + x2) / 2 / self._ancho,
                (y1 + y2) / 2 / self._alto,
                (x2 - x1) / self._ancho,
                (y2 - y1) / self._alto,
            )
            logits[0, indice, deteccion.clase] = _logit(deteccion.confianza)
        return [cajas, logits.astype(np.float32)]


CATALOGO_RF_DETR = CatalogoDeClases(
    {ID_PERSONA: ClaseObjeto.PERSONA, ID_CELULAR: ClaseObjeto.CELULAR}
)


class DetectorEspia:
    """DetectorOnnx sobre una sesión falsa que además guarda los frames que recibió."""

    def __init__(self, detecciones: Sequence[DeteccionCruda], ancho: int, alto: int) -> None:
        configuracion = ConfiguracionOnnx((0.5,) * 3, (0.25,) * 3, CATALOGO_RF_DETR, 0.0)
        self._detector = DetectorOnnx(SesionOnnxFalsa(detecciones, ancho, alto), configuracion)
        self.frames_recibidos: list[np.ndarray] = []

    def detectar(self, frame: np.ndarray) -> list[Deteccion]:
        self.frames_recibidos.append(frame)
        return self._detector.detectar(frame)
