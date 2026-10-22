"""Dobles de un modelo de Ultralytics (YOLOv8): solo la interfaz que usa el código del repo."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class DeteccionCruda:
    """Una fila de `results[0].boxes`: id de clase del modelo, caja xyxy y confianza."""

    clase: int
    caja: tuple[float, float, float, float]
    confianza: float = 0.9


class TensorFalso:
    """Imita la interfaz `.cpu().numpy()` de los tensores de Ultralytics."""

    def __init__(self, valores: Any) -> None:
        self._valores = np.asarray(valores, dtype=np.float32)

    def cpu(self) -> "TensorFalso":
        return self

    def numpy(self) -> np.ndarray:
        return self._valores


class CajasFalsas:
    def __init__(self, detecciones: Sequence[DeteccionCruda]) -> None:
        self.xyxy = TensorFalso([fila.caja for fila in detecciones] or np.empty((0, 4)))
        self.conf = TensorFalso([fila.confianza for fila in detecciones])
        self.cls = TensorFalso([fila.clase for fila in detecciones])
        self.id = None


class ResultadoFalso:
    obb = None
    masks = None

    def __init__(self, frame: np.ndarray, detecciones: Sequence[DeteccionCruda]) -> None:
        self.boxes = CajasFalsas(detecciones)
        self._frame = frame

    def plot(self) -> np.ndarray:
        return self._frame.copy()


class ModeloFalso:
    def __init__(self, detecciones: Sequence[DeteccionCruda]) -> None:
        self._detecciones = detecciones
        self.frames_recibidos: list[np.ndarray] = []
        self.opciones_recibidas: list[dict[str, Any]] = []

    def __call__(self, frame: np.ndarray, **opciones: Any) -> list[ResultadoFalso]:
        self.frames_recibidos.append(frame)
        self.opciones_recibidas.append(opciones)
        return [ResultadoFalso(frame, self._detecciones)]
