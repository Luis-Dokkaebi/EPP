"""Puerto de detección (SPEC/9 §1.3.3): lo que el tracking necesita de cualquier motor de IA."""

from typing import Protocol

import numpy as np

from src.inference.types import Deteccion


class DetectorPort(Protocol):
    def detectar(self, frame: np.ndarray) -> list[Deteccion]:
        """Detecciones del frame BGR, en coordenadas del frame, ya traducidas a ClaseObjeto."""
        ...
