"""La raíz de composición crea el motor facial verificando antes la integridad de sus modelos."""

from pathlib import Path

import pytest

from config import config as configuracion
from src import composition as composicion
from src.models.model_verifier import ModelIntegrityError

RUTAS = ("models/rostros/yunet.onnx", "models/rostros/sface.onnx")


@pytest.fixture
def rutas_configuradas(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[str, str]:
    detector, reconocedor = (str(tmp_path / ruta) for ruta in RUTAS)
    monkeypatch.setattr(configuracion, "FACE_DETECTOR_PATH", detector)
    monkeypatch.setattr(configuracion, "FACE_RECOGNIZER_PATH", reconocedor)
    return detector, reconocedor


def test_motor_facial_configurado_verifica_ambos_modelos_y_los_carga(
    monkeypatch: pytest.MonkeyPatch, rutas_configuradas: tuple[str, str]
) -> None:
    verificados: list[str] = []
    monkeypatch.setattr(composicion, "assert_model_integrity", verificados.append)
    monkeypatch.setattr(composicion, "crear_motor_facial_opencv", lambda *rutas: rutas)

    motor = composicion.crear_motor_facial_configurado()

    assert verificados == list(rutas_configuradas)
    assert motor == rutas_configuradas


def test_motor_facial_con_un_modelo_manipulado_no_se_crea(
    monkeypatch: pytest.MonkeyPatch, rutas_configuradas: tuple[str, str]
) -> None:
    def rechazar(ruta: str) -> None:
        raise ModelIntegrityError(ruta)

    monkeypatch.setattr(composicion, "assert_model_integrity", rechazar)
    monkeypatch.setattr(
        composicion, "crear_motor_facial_opencv", lambda *_: pytest.fail("no debía cargar")
    )

    with pytest.raises(ModelIntegrityError):
        composicion.crear_motor_facial_configurado()


def test_las_rutas_de_los_modelos_faciales_apuntan_a_models_rostros() -> None:
    assert Path(configuracion.FACE_DETECTOR_PATH).parts[-3:] == (
        "models",
        "rostros",
        "face_detection_yunet_2023mar.onnx",
    )
    assert Path(configuracion.FACE_RECOGNIZER_PATH).parts[-3:] == (
        "models",
        "rostros",
        "face_recognition_sface_2021dec.onnx",
    )
