"""El worker de cámara exige el hash del modelo instalado y firmado (SPEC/10 F-05, AC-T05)."""

import hashlib
import queue
from pathlib import Path
from typing import Any

import pytest
from Crypto.PublicKey import RSA

from config import config
from src.models import modelo_de_la_app as modulo
from src.tracking import camera_worker as modulo_worker
from src.tracking.camera_worker import CameraWorker
from tests.licencias_firmadas import firmar, generar_llave, publica_de

PESOS = b"pesos afinados para acme"


class ReconocedorFalso:
    def __init__(self, *_argumentos: Any, **_opciones: Any) -> None:
        self.known_face_names: list[str] = []


@pytest.fixture(scope="module")
def llave() -> RSA.RsaKey:
    return generar_llave()


@pytest.fixture
def carpeta_del_modelo(llave: RSA.RsaKey, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(modulo, "LLAVE_PUBLICA", publica_de(llave))
    monkeypatch.setattr(config, "get_faces_dir", lambda: str(tmp_path / "faces"))
    monkeypatch.setattr(modulo_worker, "FaceRecognizer", ReconocedorFalso)
    carpeta = tmp_path / "OficinaEficiencia" / "modelo"
    carpeta.mkdir(parents=True)
    return carpeta


def _instalar(carpeta: Path, firmante: RSA.RsaKey, pesos_declarados: bytes) -> None:
    entrada = {
        "archivo": "epp_acme.onnx",
        "sha256": hashlib.sha256(pesos_declarados).hexdigest(),
        "motor": "onnx",
        "version": "0.1-acme",
        "clases": {"0": "persona"},
        "media": [0.5, 0.5, 0.5],
        "desviacion": [0.5, 0.5, 0.5],
    }
    (carpeta / "epp_acme.onnx").write_bytes(PESOS)
    (carpeta / "modelo.manifest").write_text(
        firmar(firmante, {"cliente": "acme", "modelos": [entrada]}), encoding="utf-8"
    )


def _worker() -> CameraWorker:
    return CameraWorker(camera_id=0, frame_queue=queue.Queue(maxsize=2), detector=object())


def test_un_modelo_instalado_con_firma_y_hash_validos_habilita_la_camara(
    carpeta_del_modelo: Path, llave: RSA.RsaKey
) -> None:
    _instalar(carpeta_del_modelo, llave, PESOS)

    assert _worker().model_verified is True


def test_un_modelo_instalado_con_otro_hash_deshabilita_la_camara(
    carpeta_del_modelo: Path, llave: RSA.RsaKey, capsys: pytest.CaptureFixture[str]
) -> None:
    _instalar(carpeta_del_modelo, llave, b"otros pesos")

    worker = _worker()

    assert worker.model_verified is False
    assert capsys.readouterr().out.splitlines()[-2] == (
        f"[VMS][SECURITY] Modelo AI manipulado en {carpeta_del_modelo / 'epp_acme.onnx'}. "
        "Inferencia DESHABILITADA para cámara 0."
    )


def test_un_manifiesto_instalado_con_otra_firma_deshabilita_la_camara(
    carpeta_del_modelo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _instalar(carpeta_del_modelo, generar_llave(), PESOS)

    worker = _worker()

    assert worker.model_verified is False
    assert "la firma no es del proveedor" in capsys.readouterr().out


def test_un_manifiesto_instalado_sin_su_modelo_deshabilita_la_camara(
    carpeta_del_modelo: Path, llave: RSA.RsaKey
) -> None:
    _instalar(carpeta_del_modelo, llave, PESOS)
    (carpeta_del_modelo / "epp_acme.onnx").unlink()

    assert _worker().model_verified is False
