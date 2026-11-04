"""Registro y reconocimiento de empleados por su cara, sobre MotorFacialPort.

Los vectores se guardan en `.npz` (sin pickle) firmados con HMAC ligado a la máquina del DRM
(OWASP A08, CR-08). Cada archivo recuerda el motor que lo generó: los vectores de otro motor
(por ejemplo los de dlib) no son comparables y se recalculan desde las fotos.
"""

import hashlib
import hmac
import io
import logging
import os
import shutil
import zipfile
from collections.abc import Sequence

import cv2
import numpy as np

from src.recognition.ports import MotorFacialPort

_logger = logging.getLogger(__name__)

NOMBRE_DESCONOCIDO = "Unknown"
LARGO_DE_FIRMA = 32  # SHA-256
EXTENSIONES_DE_FOTO = (".jpg", ".jpeg", ".png")
SAL_DE_INTEGRIDAD = b"_oe_face_integrity_v2"
ERRORES_DE_ARCHIVO = (OSError, ValueError, KeyError, zipfile.BadZipFile)


class ArchivoDeVectoresInvalidoError(ValueError):
    """El archivo de vectores está corrupto, manipulado, es de otra máquina o de otro motor."""


def _identificador_de_maquina() -> str:
    """El mismo machine_id (WMI) que usa el DRM; el hostname se cambia demasiado fácil."""
    try:
        from src.security.drm import DRMValidator

        return str(DRMValidator().machine_id)
    except (ImportError, OSError, RuntimeError) as error:
        import uuid

        _logger.warning("[FaceRecognizer] Sin machine_id del DRM (%s).", type(error).__name__)
        return f"FALLBACK_{uuid.getnode()}"


def _clave_de_integridad() -> bytes:
    return hashlib.sha256(_identificador_de_maquina().encode("utf-8") + SAL_DE_INTEGRIDAD).digest()


def firmar(contenido: bytes) -> bytes:
    return hmac.new(_clave_de_integridad(), contenido, hashlib.sha256).digest()


def firma_valida(contenido: bytes, firma: bytes) -> bool:
    return hmac.compare_digest(firmar(contenido), firma)


def leer_imagen(ruta: str) -> np.ndarray | None:
    """Imagen BGR o None; admite rutas con acentos (cv2.imread no las abre en Windows)."""
    try:
        contenido = np.fromfile(ruta, dtype=np.uint8)
    except OSError:
        return None
    if contenido.size == 0:
        return None
    imagen: np.ndarray | None = cv2.imdecode(contenido, cv2.IMREAD_COLOR)
    return imagen


def _carpeta_por_omision() -> str:
    datos = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(datos, "OficinaEficiencia", "data", "faces")


def _motor_configurado() -> MotorFacialPort:
    from src.composition import crear_motor_facial_configurado

    return crear_motor_facial_configurado()


class FaceRecognizer:
    def __init__(
        self,
        faces_dir: str | None = None,
        encodings_file: str | None = None,
        motor: MotorFacialPort | None = None,
    ) -> None:
        self.faces_dir = faces_dir or _carpeta_por_omision()
        self.encodings_file = encodings_file or os.path.join(self.faces_dir, "encodings.npz")
        self.motor = motor or _motor_configurado()
        self.known_face_encodings: list[np.ndarray] = []
        self.known_face_names: list[str] = []
        self._encodings_mtime = 0.0
        os.makedirs(self.faces_dir, exist_ok=True)
        self.load_known_faces()

    def load_known_faces(self) -> None:
        """Lee el archivo firmado; si no sirve, recalcula los vectores desde las fotos."""
        try:
            self._leer_archivo()
            _logger.info("[FaceRecognizer] %d rostro(s) cargados.", len(self.known_face_names))
            return
        except ERRORES_DE_ARCHIVO as error:
            _logger.info("[FaceRecognizer] Se recalculan los vectores (%s).", error)
        self._codificar_carpeta()
        self.save_encodings()

    def save_encodings(self) -> None:
        """Escribe el archivo de vectores firmado (npz comprimido, sin pickle)."""
        vectores = _como_matriz(self.known_face_encodings)
        buffer = io.BytesIO()
        np.savez_compressed(
            buffer,
            encodings=vectores,
            names=np.array(self.known_face_names, dtype=str),
            motor=np.array(self.motor.identificador),
        )
        contenido = buffer.getvalue()
        with open(self.encodings_file, "wb") as archivo:
            archivo.write(firmar(contenido) + contenido)
        self._encodings_mtime = os.path.getmtime(self.encodings_file)

    def check_reload(self) -> None:
        """Recarga si otro proceso (la vista de registro) actualizó el archivo."""
        if not os.path.exists(self.encodings_file):
            return
        if os.path.getmtime(self.encodings_file) > self._encodings_mtime:
            _logger.info("[FaceRecognizer] El archivo de vectores cambió: se recarga.")
            self.load_known_faces()

    def recognize_face(self, frame: np.ndarray, bbox: Sequence[float] | None = None) -> str:
        """Nombre de la persona más parecida sobre el umbral del motor, o NOMBRE_DESCONOCIDO."""
        vector = self.motor.codificar(_recortar(frame, bbox) if bbox else frame)
        if vector is None or not self.known_face_encodings:
            return NOMBRE_DESCONOCIDO
        similitudes = [self.motor.similitud(c, vector) for c in self.known_face_encodings]
        mejor = int(np.argmax(similitudes))
        if similitudes[mejor] < self.motor.umbral_de_coincidencia:
            return NOMBRE_DESCONOCIDO
        return self.known_face_names[mejor]

    def register_face(self, image_path: str, name: str) -> bool:
        """Registra a `name` con una foto; False si no existe o no tiene cara."""
        vector = self._vector_de(image_path)
        if vector is None:
            _logger.info("[FaceRecognizer] Registro abortado: foto ausente o sin cara.")
            return False
        self._guardar_foto(image_path, name, os.path.basename(image_path))
        self._agregar(vector, name)
        self.save_encodings()
        return True

    def register_face_burst(self, image_paths: Sequence[str], name: str) -> int:
        """Registra varias fotos de una ráfaga; devuelve cuántas tenían cara."""
        registradas = 0
        for indice, ruta in enumerate(image_paths):
            vector = self._vector_de(ruta)
            if vector is None:
                continue
            self._guardar_foto(ruta, name, f"burst_{indice}.jpg")
            self._agregar(vector, name)
            registradas += 1
        if registradas:
            self.save_encodings()
        return registradas

    def delete_face(self, name: str) -> bool:
        """Quita a `name` de la memoria, del archivo de vectores y sus fotos del disco."""
        if name not in self.known_face_names:
            return False
        conservados = [i for i, nombre in enumerate(self.known_face_names) if nombre != name]
        self.known_face_encodings = [self.known_face_encodings[i] for i in conservados]
        self.known_face_names = [self.known_face_names[i] for i in conservados]
        self.save_encodings()
        shutil.rmtree(os.path.join(self.faces_dir, name), ignore_errors=True)
        return True

    def _leer_archivo(self) -> None:
        with open(self.encodings_file, "rb") as archivo:
            crudo = archivo.read()
        firma, contenido = crudo[:LARGO_DE_FIRMA], crudo[LARGO_DE_FIRMA:]
        if len(crudo) < LARGO_DE_FIRMA or not firma_valida(contenido, firma):
            raise ArchivoDeVectoresInvalidoError("firma inválida o de otra máquina")
        cargado = np.load(io.BytesIO(contenido), allow_pickle=False)
        if str(cargado["motor"]) != self.motor.identificador:
            raise ArchivoDeVectoresInvalidoError(f"vectores de otro motor ({cargado['motor']})")
        self.known_face_encodings = list(cargado["encodings"])
        self.known_face_names = [str(nombre) for nombre in cargado["names"]]
        self._encodings_mtime = os.path.getmtime(self.encodings_file)

    def _codificar_carpeta(self) -> None:
        self.known_face_encodings, self.known_face_names = [], []
        for nombre in sorted(os.listdir(self.faces_dir)):
            carpeta = os.path.join(self.faces_dir, nombre)
            if not os.path.isdir(carpeta):
                continue
            fotos = (
                a for a in sorted(os.listdir(carpeta)) if a.lower().endswith(EXTENSIONES_DE_FOTO)
            )
            for foto in fotos:
                vector = self._vector_de(os.path.join(carpeta, foto))
                if vector is not None:
                    self._agregar(vector, nombre)

    def _vector_de(self, ruta: str) -> np.ndarray | None:
        imagen = leer_imagen(ruta) if os.path.isfile(ruta) else None
        return None if imagen is None else self.motor.codificar(imagen)

    def _guardar_foto(self, origen: str, name: str, archivo: str) -> None:
        carpeta = os.path.join(self.faces_dir, name)
        os.makedirs(carpeta, exist_ok=True)
        shutil.copy(origen, os.path.join(carpeta, archivo))

    def _agregar(self, vector: np.ndarray, name: str) -> None:
        self.known_face_encodings.append(vector)
        self.known_face_names.append(name)


def _como_matriz(vectores: list[np.ndarray]) -> np.ndarray:
    if not vectores:
        return np.empty((0, 0), dtype=np.float32)
    return np.stack([np.asarray(v, dtype=np.float32).ravel() for v in vectores])


def _recortar(frame: np.ndarray, bbox: Sequence[float]) -> np.ndarray:
    alto, ancho = frame.shape[:2]
    x1, y1, x2, y2 = (int(valor) for valor in bbox)
    return frame[max(0, y1) : min(alto, y2), max(0, x1) : min(ancho, x2)]
