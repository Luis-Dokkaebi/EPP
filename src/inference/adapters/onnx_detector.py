"""Adaptador de ONNX Runtime a DetectorPort para modelos tipo DETR (SPEC/9 §1.4, ADR-001).

El modelo devuelve, por consulta, una caja (cx, cy, w, h) normalizada a [0, 1] y un logit por
clase. Los detectores tipo DETR (RF-DETR, D-FINE) no necesitan NMS.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import cv2
import numpy as np
import onnxruntime

from src.inference.types import (
    Caja,
    CajaInvalidaError,
    CatalogoDeClases,
    Deteccion,
    validar_confianza,
)

_logger = logging.getLogger(__name__)
PROVEEDOR_CPU = "CPUExecutionProvider"
MAXIMO_DE_UN_PIXEL = 255.0


class SesionOnnx(Protocol):
    """Lo que el adaptador usa de onnxruntime.InferenceSession."""

    def get_inputs(self) -> list[Any]: ...

    def run(self, salidas: Any, entradas: dict[str, np.ndarray]) -> list[np.ndarray]: ...


@dataclass(frozen=True)
class ConfiguracionOnnx:
    """Media y desviación por canal RGB (del manifiesto del modelo), catálogo y umbral."""

    media: tuple[float, float, float]
    desviacion: tuple[float, float, float]
    catalogo: CatalogoDeClases
    confianza_minima: float

    def __post_init__(self) -> None:
        validar_confianza(self.confianza_minima)


def crear_sesion(ruta_modelo: str, proveedores: Sequence[str] = (PROVEEDOR_CPU,)) -> Any:
    """InferenceSession con los proveedores pedidos: CPU por omisión; DirectML u OpenVINO (D2)."""
    return onnxruntime.InferenceSession(ruta_modelo, providers=list(proveedores))


class DetectorOnnx:
    def __init__(self, sesion: SesionOnnx, configuracion: ConfiguracionOnnx) -> None:
        self._sesion = sesion
        self._configuracion = configuracion
        entrada = sesion.get_inputs()[0]
        self._nombre_entrada: str = entrada.name
        self._alto, self._ancho = int(entrada.shape[2]), int(entrada.shape[3])

    def detectar(self, frame: np.ndarray) -> list[Deteccion]:
        cajas, logits = self._sesion.run(None, {self._nombre_entrada: self._preprocesar(frame)})
        alto, ancho = frame.shape[:2]
        confianzas = 1.0 / (1.0 + np.exp(-logits[0]))
        detecciones = (
            self._traducir(caja, fila, ancho, alto)
            for caja, fila in zip(cajas[0], confianzas, strict=True)
        )
        return [deteccion for deteccion in detecciones if deteccion is not None]

    def _preprocesar(self, frame: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(cv2.resize(frame, (self._ancho, self._alto)), cv2.COLOR_BGR2RGB)
        normalizado = (rgb / MAXIMO_DE_UN_PIXEL - self._configuracion.media) / (
            self._configuracion.desviacion
        )
        return np.ascontiguousarray(normalizado.transpose(2, 0, 1)[np.newaxis], dtype=np.float32)

    def _traducir(
        self, caja: np.ndarray, confianzas: np.ndarray, ancho: int, alto: int
    ) -> Deteccion | None:
        id_clase = int(np.argmax(confianzas))
        confianza = float(confianzas[id_clase])
        clase = self._configuracion.catalogo.clase_de(id_clase)
        if clase is None or confianza < self._configuracion.confianza_minima:
            return None
        try:
            return Deteccion(clase, confianza, _a_caja_del_frame(caja, ancho, alto))
        except CajaInvalidaError as error:
            _logger.debug("Caja degenerada descartada: %s", error)
            return None


def _a_caja_del_frame(caja: np.ndarray, ancho: int, alto: int) -> Caja:
    centro_x, centro_y, ancho_caja, alto_caja = (float(valor) for valor in caja)
    return Caja(
        x1=min(max((centro_x - ancho_caja / 2) * ancho, 0.0), ancho),
        y1=min(max((centro_y - alto_caja / 2) * alto, 0.0), alto),
        x2=min(max((centro_x + ancho_caja / 2) * ancho, 0.0), ancho),
        y2=min(max((centro_y + alto_caja / 2) * alto, 0.0), alto),
    )
