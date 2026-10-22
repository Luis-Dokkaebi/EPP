# tests/test_model_verifier.py
# TASK-5.2 DoD: reemplazar yolov8n.pt por un modelo falso detiene el tracking.

import os
import sys
import hashlib
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.manifiesto_aprobado import MODELOS_APROBADOS
from src.models.model_verifier import (
    compute_model_hash, verify_model, assert_model_integrity,
    ModelIntegrityError,
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'yolov8n.pt')


@pytest.mark.skipif(not os.path.exists(MODEL_PATH), reason="yolov8n.pt no presente")
def test_real_model_matches_embedded_hash():
    """El modelo distribuido coincide con el hash pre-aprobado embebido."""
    assert verify_model(MODEL_PATH) is True
    assert compute_model_hash(MODEL_PATH) == MODELOS_APROBADOS["yolov8n.pt"]


def test_tampered_model_is_rejected(tmp_path):
    """Un modelo manipulado (backdoor) es rechazado y aborta el tracking."""
    fake = tmp_path / "yolov8n.pt"
    fake.write_bytes(b"FAKE_MODEL_WITH_BACKDOOR" * 100)

    assert verify_model(str(fake)) is False
    with pytest.raises(ModelIntegrityError):
        assert_model_integrity(str(fake))


def test_compute_hash_is_sha256(tmp_path):
    f = tmp_path / "m.bin"
    f.write_bytes(b"abc123")
    assert compute_model_hash(str(f)) == hashlib.sha256(b"abc123").hexdigest()


def test_missing_model_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        compute_model_hash(str(tmp_path / "nope.pt"))


def test_camera_worker_disabled_when_model_tampered(monkeypatch, tmp_path):
    """CameraWorker.run() no arranca si la verificacion del modelo falla."""
    # Stub config para no exigir Tenant activo ni face_recognition real.
    import config.config as cfg
    monkeypatch.setattr(cfg, "get_faces_dir", lambda: str(tmp_path / "faces"))
    monkeypatch.setattr(cfg, "MODEL_PATH", str(tmp_path / "yolov8n.pt"))
    (tmp_path / "yolov8n.pt").write_bytes(b"NOT THE REAL MODEL")

    import queue
    from src.tracking.camera_worker import CameraWorker
    w = CameraWorker(
        camera_id=0, frame_queue=queue.Queue(maxsize=2), detector=object(), fps_limit=15
    )
    assert w.model_verified is False
    # run() debe retornar inmediatamente sin tocar cv2.
    w.run()
    assert w.running is False
