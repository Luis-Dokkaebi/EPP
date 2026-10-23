"""Evidencia anotada de las infracciones de EPP (SPEC/9 §6.2, C-08; AC-015).

Adaptador de AlmacenEvidenciasPort: dibuja la caja de la persona en rojo con el elemento
faltante y guarda un JPG en <snapshots del tenant>/epp/AAAA-MM-DD/. El nombre del archivo lleva
la hora, el track y el elemento, nunca el nombre del empleado. Vive en la capa de adaptadores
porque usa cv2.
"""

from pathlib import Path

import cv2
import numpy as np

from src.ppe.domain.elementos import ElementoEPP
from src.ppe.domain.geometria import Caja
from src.ppe.domain.infracciones import InfraccionIniciada

ROJO = (0, 0, 255)
GROSOR_CAJA = 3
ESCALA_TEXTO = 0.6
GROSOR_TEXTO = 2
SEPARACION_TEXTO = 8


class EvidenciaNoGuardadaError(OSError):
    """OpenCV no pudo escribir la imagen de la evidencia."""


def anotar_evidencia(imagen: np.ndarray, caja: Caja, faltante: ElementoEPP) -> np.ndarray:
    """Copia del frame con la persona en rojo y el rótulo del elemento que le falta."""
    anotada = imagen.copy()
    esquina = (round(caja.x1), round(caja.y1))
    cv2.rectangle(anotada, esquina, (round(caja.x2), round(caja.y2)), ROJO, GROSOR_CAJA)
    origen = (esquina[0], esquina[1] - SEPARACION_TEXTO)
    fuente = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(anotada, f"Sin {faltante.value}", origen, fuente, ESCALA_TEXTO, ROJO, GROSOR_TEXTO)
    return anotada


class AlmacenEvidenciasCv2:
    """Implementa AlmacenEvidenciasPort sobre la carpeta de snapshots del tenant."""

    def __init__(self, carpeta_snapshots: Path) -> None:
        self._carpeta = carpeta_snapshots

    def guardar_evidencia(
        self, imagen: object, caja_persona: Caja, infraccion: InfraccionIniciada
    ) -> str:
        if not isinstance(imagen, np.ndarray):
            raise TypeError(f"La evidencia necesita un frame numpy; llegó {type(imagen).__name__}")
        incumplimiento = infraccion.incumplimiento
        anotada = anotar_evidencia(imagen, caja_persona, incumplimiento.elemento)
        nombre = f"{infraccion.inicio:%H%M%S_%f}_t{incumplimiento.track_id}"
        ruta = self._carpeta / "epp" / f"{infraccion.inicio:%Y-%m-%d}"
        ruta.mkdir(parents=True, exist_ok=True)
        archivo = ruta / f"{nombre}_{incumplimiento.elemento.value}.jpg"
        if not cv2.imwrite(str(archivo), anotada):
            raise EvidenciaNoGuardadaError(f"No se pudo guardar la evidencia en {archivo}")
        return str(archivo)
