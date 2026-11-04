"""Doble de MotorFacialPort: el vector de una imagen es el color de su primer píxel.

Una imagen negra no tiene cara. Así las pruebas escriben imágenes chicas reales en tmp_path
sin cargar los modelos ONNX (CLAUDE.md §16).
"""

import cv2
import numpy as np

from src.recognition.ports import CaraLocalizada

UMBRAL_FALSO = 0.5


class MotorFacialFalso:
    identificador = "motor-falso-v1"
    umbral_de_coincidencia = UMBRAL_FALSO

    def __init__(self) -> None:
        self.imagenes_codificadas: list[np.ndarray] = []

    def localizar(self, imagen_bgr: np.ndarray) -> list[CaraLocalizada]:
        if self.codificar(imagen_bgr) is None:
            return []
        return [CaraLocalizada(0.0, 0.0, 2.0, 2.0, ((1.0, 1.0),), 0.9)]

    def codificar(self, imagen_bgr: np.ndarray) -> np.ndarray | None:
        self.imagenes_codificadas.append(imagen_bgr)
        if imagen_bgr.size == 0 or not imagen_bgr[0, 0].any():
            return None
        vector: np.ndarray = imagen_bgr[0, 0].astype(np.float32)
        return vector

    def similitud(self, conocida: np.ndarray, candidata: np.ndarray) -> float:
        return 1.0 / (1.0 + float(np.abs(np.asarray(conocida) - np.asarray(candidata)).sum()))


def escribir_imagen(ruta: str, color: tuple[int, int, int]) -> str:
    """PNG de 4x4 de un color; con imencode + tofile para admitir rutas unicode."""
    imagen = np.full((4, 4, 3), color, dtype=np.uint8)
    _, contenido = cv2.imencode(".png", imagen)
    contenido.tofile(ruta)
    return ruta
