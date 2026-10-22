"""Anotador de frames propio (SPEC/9 §1.3.5): dibuja las detecciones de cualquier motor.

Reemplaza a `results[0].plot()` de Ultralytics, así el dibujo no depende del motor de IA.
Vive en la capa de adaptadores porque usa cv2.
"""

from collections.abc import Sequence

import cv2
import numpy as np

from src.inference.types import ClaseObjeto, Deteccion

COLOR_EPP = (0, 255, 255)
COLORES: dict[ClaseObjeto, tuple[int, int, int]] = {
    **dict.fromkeys(ClaseObjeto, COLOR_EPP),
    ClaseObjeto.PERSONA: (0, 255, 0),
    ClaseObjeto.CELULAR: (0, 0, 255),
}
GROSOR_CAJA = 2
ESCALA_TEXTO = 0.5
GROSOR_TEXTO = 1
SEPARACION_TEXTO = 5


class AnotadorDeFrames:
    def anotar(self, frame: np.ndarray, detecciones: Sequence[Deteccion]) -> np.ndarray:
        """Copia del frame con cada detección dibujada; el frame original no se modifica."""
        anotado = frame.copy()
        for deteccion in detecciones:
            _dibujar(anotado, deteccion)
        return anotado


def _dibujar(frame: np.ndarray, deteccion: Deteccion) -> None:
    caja = deteccion.caja
    esquina = (round(caja.x1), round(caja.y1))
    color = COLORES[deteccion.clase]
    cv2.rectangle(frame, esquina, (round(caja.x2), round(caja.y2)), color, GROSOR_CAJA)
    etiqueta = f"{deteccion.clase.value} {deteccion.confianza:.2f}"
    origen = (esquina[0], esquina[1] - SEPARACION_TEXTO)
    fuente = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, etiqueta, origen, fuente, ESCALA_TEXTO, color, GROSOR_TEXTO)
