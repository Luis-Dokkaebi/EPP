"""Reconocimiento facial con OpenCV: YuNet (MIT) detecta y SFace (Apache-2.0) codifica.

Reemplaza a `face_recognition`/dlib, cuyo modelo de 68 puntos (iBUG 300-W) restringe el uso
comercial (docs/legal/revision_d9.md §3). Los dos modelos son ONNX y corren con el `cv2` que
la app ya usa, sin compilar dlib.
"""

import os
from typing import Any, Protocol

import cv2
import numpy as np

from src.recognition.ports import CaraLocalizada

IDENTIFICADOR = "yunet-2023mar+sface-2021dec"
# Umbral de similitud coseno que publica opencv_zoo para SFace (LFW).
UMBRAL_COSENO_SFACE = 0.363
CONFIANZA_MINIMA_POR_OMISION = 0.8
UMBRAL_NMS = 0.3
MAXIMO_DE_CANDIDATAS = 5000
TAMANO_INICIAL = (320, 320)
# YuNet ve caras de ~10 a 300 px: las fotos de registro (hasta 2048 px) se reducen antes.
LADO_MAXIMO = 640
COLUMNAS_DE_PUNTOS = slice(4, 14)
COLUMNA_DE_CONFIANZA = 14


class ModeloFacialNoEncontradoError(FileNotFoundError):
    """Falta el archivo ONNX del detector o del reconocedor de caras."""


class DetectorDeCaras(Protocol):
    """Lo que el adaptador usa de cv2.FaceDetectorYN."""

    def setInputSize(self, tamano: tuple[int, int]) -> None: ...  # noqa: N802 - API de cv2

    def detect(self, imagen: np.ndarray) -> tuple[Any, np.ndarray | None]: ...


class ReconocedorDeCaras(Protocol):
    """Lo que el adaptador usa de cv2.FaceRecognizerSF."""

    def alignCrop(self, imagen: np.ndarray, fila: np.ndarray) -> np.ndarray: ...  # noqa: N802

    def feature(self, alineada: np.ndarray) -> np.ndarray: ...

    def match(self, conocida: np.ndarray, candidata: np.ndarray, tipo: int) -> float: ...


class MotorFacialOpenCV:
    """MotorFacialPort con los modelos de opencv_zoo."""

    identificador = IDENTIFICADOR
    umbral_de_coincidencia = UMBRAL_COSENO_SFACE

    def __init__(self, detector: DetectorDeCaras, reconocedor: ReconocedorDeCaras) -> None:
        self._detector = detector
        self._reconocedor = reconocedor

    def localizar(self, imagen_bgr: np.ndarray) -> list[CaraLocalizada]:
        """Caras en coordenadas de la imagen original, aunque se detecten sobre una reducida."""
        reducida, escala = _reducir(imagen_bgr)
        return [_a_cara(fila, escala) for fila in self._filas(reducida)]

    def codificar(self, imagen_bgr: np.ndarray) -> np.ndarray | None:
        """Vector de la cara más grande de la imagen, o None si no hay ninguna."""
        reducida, _ = _reducir(imagen_bgr)
        filas = self._filas(reducida)
        if not filas:
            return None
        mas_grande = max(filas, key=lambda fila: float(fila[2] * fila[3]))
        alineada = self._reconocedor.alignCrop(reducida, mas_grande)
        vector: np.ndarray = self._reconocedor.feature(alineada).ravel()
        return vector.astype(np.float32, copy=True)

    def similitud(self, conocida: np.ndarray, candidata: np.ndarray) -> float:
        """Similitud coseno: 1 es la misma cara; coincide desde `umbral_de_coincidencia`."""
        return float(
            self._reconocedor.match(
                _fila_float32(conocida), _fila_float32(candidata), cv2.FaceRecognizerSF_FR_COSINE
            )
        )

    def _filas(self, imagen_bgr: np.ndarray) -> list[np.ndarray]:
        alto, ancho = imagen_bgr.shape[:2]
        if alto == 0 or ancho == 0:
            return []
        self._detector.setInputSize((ancho, alto))
        _, caras = self._detector.detect(imagen_bgr)
        return [] if caras is None else list(caras)


def _fila_float32(vector: np.ndarray) -> np.ndarray:
    return np.asarray(vector, dtype=np.float32).reshape(1, -1)


def _reducir(imagen_bgr: np.ndarray) -> tuple[np.ndarray, float]:
    """La imagen con su lado mayor en LADO_MAXIMO como mucho, y el factor para volver."""
    lado_mayor = max(imagen_bgr.shape[:2])
    if lado_mayor <= LADO_MAXIMO:
        return imagen_bgr, 1.0
    factor = LADO_MAXIMO / lado_mayor
    alto, ancho = imagen_bgr.shape[:2]
    tamano = (round(ancho * factor), round(alto * factor))
    return cv2.resize(imagen_bgr, tamano, interpolation=cv2.INTER_AREA), 1.0 / factor


def _a_cara(fila: np.ndarray, escala: float) -> CaraLocalizada:
    puntos = fila[COLUMNAS_DE_PUNTOS].reshape(-1, 2) * escala
    return CaraLocalizada(
        x=float(fila[0]) * escala,
        y=float(fila[1]) * escala,
        ancho=float(fila[2]) * escala,
        alto=float(fila[3]) * escala,
        puntos=tuple((float(px), float(py)) for px, py in puntos),
        confianza=float(fila[COLUMNA_DE_CONFIANZA]),
    )


def _exigir_archivo(ruta: str) -> None:
    if not os.path.isfile(ruta):
        raise ModeloFacialNoEncontradoError(f"Modelo facial no encontrado: {ruta}")


def crear_motor_facial_opencv(
    ruta_detector: str,
    ruta_reconocedor: str,
    confianza_minima: float = CONFIANZA_MINIMA_POR_OMISION,
) -> MotorFacialOpenCV:
    """Carga YuNet y SFace desde sus ONNX; falla con error tipado si falta alguno."""
    _exigir_archivo(ruta_detector)
    _exigir_archivo(ruta_reconocedor)
    detector = cv2.FaceDetectorYN.create(
        ruta_detector, "", TAMANO_INICIAL, confianza_minima, UMBRAL_NMS, MAXIMO_DE_CANDIDATAS
    )
    reconocedor = cv2.FaceRecognizerSF.create(ruta_reconocedor, "")
    return MotorFacialOpenCV(detector, reconocedor)
