"""Puerto del reconocimiento facial: el resto de la app no conoce el motor (YuNet + SFace)."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class CaraLocalizada:
    """Caja en píxeles, los puntos de referencia del motor y la confianza de la detección."""

    x: float
    y: float
    ancho: float
    alto: float
    puntos: tuple[tuple[float, float], ...]
    confianza: float


class MotorFacialPort(Protocol):
    """Detecta caras, las convierte en vectores y compara vectores del mismo motor."""

    @property
    def identificador(self) -> str:
        """Nombre y versión de los modelos: los vectores de motores distintos no se comparan."""
        ...

    @property
    def umbral_de_coincidencia(self) -> float:
        """Similitud mínima para considerar que dos vectores son de la misma persona."""
        ...

    def localizar(self, imagen_bgr: np.ndarray) -> list[CaraLocalizada]: ...

    def codificar(self, imagen_bgr: np.ndarray) -> np.ndarray | None: ...

    def similitud(self, conocida: np.ndarray, candidata: np.ndarray) -> float: ...
