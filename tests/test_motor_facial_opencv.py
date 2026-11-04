"""Adaptador OpenCV YuNet + SFace del puerto de reconocimiento facial (reemplaza a dlib).

Los modelos reales no se cargan: se inyectan dobles con la misma interfaz que
cv2.FaceDetectorYN y cv2.FaceRecognizerSF (CLAUDE.md §16).
"""

from pathlib import Path

import numpy as np
import pytest

from src.recognition.motor_facial_opencv import (
    ModeloFacialNoEncontradoError,
    MotorFacialOpenCV,
    crear_motor_facial_opencv,
)
from src.recognition.ports import CaraLocalizada

DIMENSION_SFACE = 128
UMBRAL_COSENO_SFACE = 0.363


def _fila_yunet(x: float, y: float, ancho: float, alto: float, confianza: float) -> list[float]:
    puntos = [x + 1, y + 1, x + 2, y + 1, x + 1.5, y + 2, x + 1, y + 3, x + 2, y + 3]
    return [x, y, ancho, alto, *puntos, confianza]


class DetectorFalso:
    def __init__(self, filas: list[list[float]] | None) -> None:
        self._caras = None if filas is None else np.array(filas, dtype=np.float32)
        self.tamano_de_entrada: tuple[int, int] | None = None

    def setInputSize(self, tamano: tuple[int, int]) -> None:  # noqa: N802 - interfaz de cv2
        self.tamano_de_entrada = tamano

    def detect(self, imagen: np.ndarray) -> tuple[int, np.ndarray | None]:
        self.imagen_recibida = imagen
        return 1, self._caras


class ReconocedorFalso:
    def __init__(self) -> None:
        self.filas_alineadas: list[np.ndarray] = []

    def alignCrop(self, imagen: np.ndarray, fila: np.ndarray) -> np.ndarray:  # noqa: N802
        self.filas_alineadas.append(fila)
        return np.full((112, 112, 3), int(fila[2]) % 256, dtype=np.uint8)

    def feature(self, alineada: np.ndarray) -> np.ndarray:
        return np.full((1, DIMENSION_SFACE), float(alineada[0, 0, 0]), dtype=np.float32)

    def match(self, conocida: np.ndarray, candidata: np.ndarray, tipo: int) -> float:
        self.formas_comparadas = (conocida.shape, candidata.shape)
        a, b = conocida.ravel(), candidata.ravel()
        return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


@pytest.fixture
def imagen() -> np.ndarray:
    return np.zeros((240, 320, 3), dtype=np.uint8)


def _motor(filas: list[list[float]] | None) -> tuple[MotorFacialOpenCV, DetectorFalso]:
    detector = DetectorFalso(filas)
    return MotorFacialOpenCV(detector, ReconocedorFalso()), detector


def test_localizar_ajusta_la_entrada_del_detector_al_tamano_de_la_imagen(imagen) -> None:
    motor, detector = _motor([_fila_yunet(10, 20, 30, 40, 0.9)])

    motor.localizar(imagen)

    assert detector.tamano_de_entrada == (320, 240)


def test_localizar_devuelve_caja_cinco_puntos_y_confianza(imagen) -> None:
    motor, _ = _motor([_fila_yunet(10, 20, 30, 40, 0.9)])

    caras = motor.localizar(imagen)

    assert caras == [
        CaraLocalizada(
            x=10.0,
            y=20.0,
            ancho=30.0,
            alto=40.0,
            puntos=((11.0, 21.0), (12.0, 21.0), (11.5, 22.0), (11.0, 23.0), (12.0, 23.0)),
            confianza=pytest.approx(0.9),
        )
    ]


def test_localizar_sin_caras_devuelve_lista_vacia(imagen) -> None:
    motor, _ = _motor(None)

    assert motor.localizar(imagen) == []


@pytest.mark.parametrize(
    "vacia",
    [
        np.zeros((0, 0, 3), dtype=np.uint8),
        np.zeros((10, 0, 3), dtype=np.uint8),
        np.zeros((0, 10, 3), dtype=np.uint8),
    ],
    ids=["sin_pixeles", "sin_ancho", "sin_alto"],
)
def test_imagen_vacia_no_se_localiza_ni_se_codifica(vacia: np.ndarray) -> None:
    motor, detector = _motor([_fila_yunet(10, 20, 30, 40, 0.9)])

    assert motor.localizar(vacia) == []
    assert motor.codificar(vacia) is None
    assert detector.tamano_de_entrada is None


def test_codificar_sin_caras_devuelve_none(imagen) -> None:
    motor, _ = _motor(None)

    assert motor.codificar(imagen) is None


def test_codificar_usa_la_cara_mas_grande(imagen) -> None:
    detector = DetectorFalso([_fila_yunet(0, 0, 20, 20, 0.99), _fila_yunet(50, 50, 60, 60, 0.7)])
    reconocedor = ReconocedorFalso()
    motor = MotorFacialOpenCV(detector, reconocedor)

    codificacion = motor.codificar(imagen)

    assert codificacion is not None
    assert reconocedor.filas_alineadas[0][2] == pytest.approx(60.0)
    assert codificacion.shape == (DIMENSION_SFACE,)
    assert codificacion.dtype == np.float32


def test_similitud_de_codificaciones_iguales_es_uno() -> None:
    motor, _ = _motor(None)
    codificacion = np.arange(1, DIMENSION_SFACE + 1, dtype=np.float32)

    assert motor.similitud(codificacion, codificacion) == pytest.approx(1.0)


def test_similitud_acepta_codificaciones_guardadas_en_float64() -> None:
    motor, _ = _motor(None)
    guardada = np.ones(DIMENSION_SFACE, dtype=np.float64)

    assert motor.similitud(guardada, -guardada) == pytest.approx(-1.0)


def test_umbral_e_identificador_son_los_de_sface() -> None:
    motor, _ = _motor(None)

    assert motor.umbral_de_coincidencia == pytest.approx(UMBRAL_COSENO_SFACE)
    assert motor.identificador == "yunet-2023mar+sface-2021dec"


def test_crear_motor_sin_el_modelo_del_detector_falla_con_error_tipado(tmp_path: Path) -> None:
    reconocedor = tmp_path / "sface.onnx"
    reconocedor.write_bytes(b"x")

    with pytest.raises(
        ModeloFacialNoEncontradoError, match=r"^Modelo facial no encontrado: .*yunet"
    ):
        crear_motor_facial_opencv(str(tmp_path / "yunet.onnx"), str(reconocedor))


def test_crear_motor_sin_el_modelo_del_reconocedor_falla_con_error_tipado(tmp_path: Path) -> None:
    detector = tmp_path / "yunet.onnx"
    detector.write_bytes(b"x")

    with pytest.raises(
        ModeloFacialNoEncontradoError, match=r"^Modelo facial no encontrado: .*sface"
    ):
        crear_motor_facial_opencv(str(detector), str(tmp_path / "sface.onnx"))


@pytest.fixture
def creaciones(tmp_path, monkeypatch) -> dict[str, tuple[object, ...]]:
    """Reemplaza las fábricas de cv2 y registra con qué argumentos se llamaron."""
    for nombre in ("yunet.onnx", "sface.onnx"):
        (tmp_path / nombre).write_bytes(b"x")
    llamadas: dict[str, tuple[object, ...]] = {}

    def fabrica(clave: str, doble: object):
        return lambda *argumentos: llamadas.setdefault(clave, argumentos) and doble

    monkeypatch.setattr("cv2.FaceDetectorYN.create", fabrica("detector", DetectorFalso(None)))
    monkeypatch.setattr("cv2.FaceRecognizerSF.create", fabrica("reconocedor", ReconocedorFalso()))
    return llamadas


def test_crear_motor_construye_detector_y_reconocedor_de_opencv(tmp_path, creaciones) -> None:
    yunet, sface = str(tmp_path / "yunet.onnx"), str(tmp_path / "sface.onnx")

    motor = crear_motor_facial_opencv(yunet, sface, confianza_minima=0.75)

    assert isinstance(motor, MotorFacialOpenCV)
    assert creaciones["detector"] == (yunet, "", (320, 320), 0.75, 0.3, 5000)
    assert creaciones["reconocedor"] == (sface, "")


def test_crear_motor_sin_confianza_exige_0_8_al_detector(tmp_path, creaciones) -> None:
    crear_motor_facial_opencv(str(tmp_path / "yunet.onnx"), str(tmp_path / "sface.onnx"))

    assert creaciones["detector"][3] == pytest.approx(0.8)


def test_codificar_elige_por_area_y_no_por_alto_ni_por_ancho(imagen) -> None:
    ancha_y_baja = _fila_yunet(0, 0, 60, 20, 0.9)
    angosta_y_alta = _fila_yunet(50, 50, 10, 30, 0.9)
    reconocedor = ReconocedorFalso()
    motor = MotorFacialOpenCV(DetectorFalso([angosta_y_alta, ancha_y_baja]), reconocedor)

    motor.codificar(imagen)

    assert reconocedor.filas_alineadas[0][2] == pytest.approx(60.0)


def test_el_vector_devuelto_no_comparte_memoria_con_el_reconocedor(imagen) -> None:
    class ReconocedorConBuffer(ReconocedorFalso):
        buffer = np.ones((1, DIMENSION_SFACE), dtype=np.float32)

        def feature(self, alineada: np.ndarray) -> np.ndarray:
            return self.buffer

    reconocedor = ReconocedorConBuffer()
    motor = MotorFacialOpenCV(DetectorFalso([_fila_yunet(1, 1, 5, 5, 0.9)]), reconocedor)

    vector = motor.codificar(imagen)
    reconocedor.buffer[0, 0] = 7.0

    assert vector is not None
    assert vector[0] == 1.0


def test_similitud_compara_filas_de_1_por_128() -> None:
    reconocedor = ReconocedorFalso()
    motor = MotorFacialOpenCV(DetectorFalso(None), reconocedor)
    vector = np.ones(DIMENSION_SFACE, dtype=np.float32)

    motor.similitud(vector, vector)

    assert reconocedor.formas_comparadas == ((1, DIMENSION_SFACE), (1, DIMENSION_SFACE))


def test_imagen_grande_se_reduce_y_las_caras_vuelven_a_su_escala() -> None:
    # YuNet solo ve caras de ~10 a 300 px: una foto de registro de 2048 px se reduce antes.
    motor, detector = _motor([_fila_yunet(10, 20, 30, 40, 0.9)])
    grande = np.zeros((1280, 2560, 3), dtype=np.uint8)

    caras = motor.localizar(grande)

    assert detector.tamano_de_entrada == (640, 320)
    assert (caras[0].x, caras[0].y, caras[0].ancho, caras[0].alto) == (40.0, 80.0, 120.0, 160.0)
    assert caras[0].puntos[0] == (44.0, 84.0)
    assert caras[0].confianza == pytest.approx(0.9)


def test_imagen_en_el_limite_no_se_reduce_ni_se_copia() -> None:
    motor, detector = _motor(None)
    limite = np.zeros((640, 640, 3), dtype=np.uint8)

    motor.localizar(limite)

    assert detector.tamano_de_entrada == (640, 640)
    assert detector.imagen_recibida is limite


def test_codificar_imagen_grande_alinea_sobre_la_imagen_reducida() -> None:
    detector = DetectorFalso([_fila_yunet(10, 20, 30, 40, 0.9)])
    reconocedor = ReconocedorFalso()
    motor = MotorFacialOpenCV(detector, reconocedor)

    motor.codificar(np.zeros((1280, 2560, 3), dtype=np.uint8))

    assert reconocedor.filas_alineadas[0][2] == pytest.approx(30.0)
