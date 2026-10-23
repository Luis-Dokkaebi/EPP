import sys
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helper: supervision-compatible Detections stub
# ---------------------------------------------------------------------------

class _FakeDetections:
    """Minimal stub that mimics sv.Detections boolean-index behaviour."""

    def __init__(self, class_id, confidence, xyxy=None):
        self.class_id  = np.asarray(class_id)
        self.confidence = np.asarray(confidence, dtype=float)
        n = len(self.class_id)
        self.xyxy = np.asarray(xyxy, dtype=float) if xyxy is not None else np.zeros((n, 4))

    def __getitem__(self, mask):
        return _FakeDetections(
            self.class_id[mask],
            self.confidence[mask],
            self.xyxy[mask],
        )


@pytest.fixture(autouse=True)
def _mock_ml_modules():
    """Prevent ultralytics / supervision from being loaded for real."""
    sv_mock = MagicMock()
    ul_mock = MagicMock()
    with patch.dict(sys.modules, {"ultralytics": ul_mock, "supervision": sv_mock}):
        yield sv_mock, ul_mock
    # _make_detector recarga el módulo con dobles: se recarga de nuevo con los módulos reales
    # para no contaminar a las pruebas que corran después (orden aleatorio, CLAUDE.md §4).
    import importlib
    import src.detection.person_detector as _pd_mod

    importlib.reload(_pd_mod)


# Re-import PersonDetector inside tests so the patched modules are active.
def _make_detector(sv_mock, ul_mock, fake_dets, confidence_threshold=0.4):
    """Build a PersonDetector whose YOLO model returns fake_dets."""
    sv_mock.Detections.from_ultralytics.return_value = fake_dets
    model_mock = MagicMock(return_value=[MagicMock()])
    ul_mock.YOLO.return_value = model_mock

    # Import (or reimport) with mocks in place
    import importlib
    import src.detection.person_detector as _pd_mod
    importlib.reload(_pd_mod)

    detector = _pd_mod.PersonDetector(model_path="fake.pt", confidence_threshold=confidence_threshold)
    return detector


def test_detect_keeps_only_person_and_phone_classes(_mock_ml_modules):
    sv_mock, ul_mock = _mock_ml_modules
    fake = _FakeDetections(
        class_id  = [0, 67, 1, 2],    # person, phone, bicycle, car
        confidence = [0.9, 0.8, 0.7, 0.6],
    )
    detector = _make_detector(sv_mock, ul_mock, fake)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(frame)

    assert set(result.class_id.tolist()).issubset({0, 67})
    assert len(result.class_id) == 2


def test_detect_removes_low_confidence_detections(_mock_ml_modules):
    sv_mock, ul_mock = _mock_ml_modules
    fake = _FakeDetections(
        class_id  = [0, 0, 67],
        confidence = [0.9, 0.2, 0.8],   # middle one is below threshold 0.4
    )
    detector = _make_detector(sv_mock, ul_mock, fake, confidence_threshold=0.4)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(frame)

    assert all(c > 0.4 for c in result.confidence)
    assert len(result.confidence) == 2


def test_detect_returns_empty_when_no_relevant_classes(_mock_ml_modules):
    sv_mock, ul_mock = _mock_ml_modules
    fake = _FakeDetections(
        class_id  = [1, 2, 3],   # no persons or phones
        confidence = [0.9, 0.8, 0.7],
    )
    detector = _make_detector(sv_mock, ul_mock, fake)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(frame)

    assert len(result.class_id) == 0
