import sys
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _mock_supervision():
    sv_mock = MagicMock()
    with patch.dict(sys.modules, {"supervision": sv_mock}):
        yield sv_mock


def _make_tracker(sv_mock):
    import importlib
    import src.tracking.person_tracker as _pt_mod
    importlib.reload(_pt_mod)
    return _pt_mod.PersonTracker(), sv_mock


def test_update_delegates_to_bytetrack(_mock_supervision):
    tracker, sv_mock = _make_tracker(_mock_supervision)

    fake_input = MagicMock()
    fake_output = MagicMock()
    tracker.tracker.update_with_detections.return_value = fake_output

    result = tracker.update(fake_input)

    tracker.tracker.update_with_detections.assert_called_once_with(fake_input)
    assert result is fake_output


def test_update_returns_tracked_detections(_mock_supervision):
    tracker, sv_mock = _make_tracker(_mock_supervision)

    expected = MagicMock()
    tracker.tracker.update_with_detections.return_value = expected

    assert tracker.update(MagicMock()) is expected
