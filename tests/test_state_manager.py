import time
import pytest
import numpy as np
from unittest.mock import MagicMock

from src.analysis.state_manager import StateManager


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.insert_state = MagicMock()
    db.update_attendance = MagicMock()
    return db


@pytest.fixture
def manager(mock_db):
    return StateManager(
        db_manager=mock_db,
        history_size=10,
        movement_threshold=5.0,
        lunch_timeout=1800,
    )


def _track(name, x=150.0, y=150.0, bbox=(100, 100, 200, 200), zone="Z", inside=True):
    return [{"name": name, "x": x, "y": y, "bbox": bbox, "zone": zone, "inside": inside}]


# ---------------------------------------------------------------------------
# get_color_for_state
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state,expected_color", [
    ("Activo",        (0, 255, 0)),
    ("Inactivo",      (0, 255, 255)),
    ("En traslado",   (255, 165, 0)),
    ("En el celular", (0, 0, 255)),
    ("Tiempo fuera",  (128, 128, 128)),
    ("Hora de comer", (255, 0, 255)),
    ("Desconocido",   (255, 255, 255)),
])
def test_get_color_for_known_state(manager, state, expected_color):
    assert manager.get_color_for_state(state) == expected_color


def test_get_color_for_unknown_state_returns_white(manager):
    assert manager.get_color_for_state("EstadoInexistente") == (255, 255, 255)


# ---------------------------------------------------------------------------
# get_state
# ---------------------------------------------------------------------------

def test_get_state_returns_desconocido_for_new_employee(manager):
    assert manager.get_state("NuevoEmpleado") == "Desconocido"


def test_get_state_returns_state_after_first_frame(manager):
    manager.process_frame(time.time(), _track("Juan"), [])
    assert manager.get_state("Juan") != "Desconocido"


# ---------------------------------------------------------------------------
# process_frame — Unknown employees are skipped
# ---------------------------------------------------------------------------

def test_process_frame_skips_unknown_name(manager, mock_db):
    manager.process_frame(time.time(), _track("Unknown"), [])
    assert "Unknown" not in manager.employees
    mock_db.insert_state.assert_not_called()


def test_process_frame_skips_unknown_does_not_call_attendance(manager, mock_db):
    manager.process_frame(time.time(), _track("Unknown"), [])
    mock_db.update_attendance.assert_not_called()


# ---------------------------------------------------------------------------
# process_frame — employee registration
# ---------------------------------------------------------------------------

def test_process_frame_registers_new_employee(manager, mock_db):
    manager.process_frame(time.time(), _track("Ana"), [])
    assert "Ana" in manager.employees
    mock_db.update_attendance.assert_called_with("Ana")


def test_process_frame_calls_insert_state_on_first_seen(manager, mock_db):
    manager.process_frame(time.time(), _track("Bob"), [])
    mock_db.insert_state.assert_any_call("Bob", "Inicializando")


# ---------------------------------------------------------------------------
# _determine_state — phone detection (highest priority)
# ---------------------------------------------------------------------------

def test_determine_state_phone_overlap_returns_en_el_celular(manager):
    person_bbox = (100, 100, 200, 200)
    phone_bbox  = (150, 150, 180, 180)   # overlaps
    manager.process_frame(time.time(), _track("Jose", bbox=person_bbox), [phone_bbox])
    assert manager.get_state("Jose") == "En el celular"


def test_determine_state_no_phone_overlap_does_not_trigger(manager):
    person_bbox = (100, 100, 200, 200)
    phone_bbox  = (500, 500, 600, 600)   # far away
    manager.process_frame(time.time(), _track("Rosa", bbox=person_bbox, inside=False), [phone_bbox])
    assert manager.get_state("Rosa") == "En traslado"


# ---------------------------------------------------------------------------
# _determine_state — En traslado (outside zone)
# ---------------------------------------------------------------------------

def test_determine_state_outside_zone_returns_en_traslado(manager):
    manager.process_frame(time.time(), _track("Diego", inside=False), [])
    assert manager.get_state("Diego") == "En traslado"


# ---------------------------------------------------------------------------
# _determine_state — Activo / Inactivo
# ---------------------------------------------------------------------------

def _add_employee_with_positions(manager, name, positions):
    manager.employees[name] = {
        "positions": list(positions),
        "last_seen": time.time(),
        "current_state": "Activo",
        "last_zone": "Z",
        "on_lunch": False,
    }
    return manager.employees[name]


def test_determine_state_active_with_high_movement(manager):
    emp = _add_employee_with_positions(
        manager, "Marta",
        [(100 + i * 10, 100 + i * 10) for i in range(10)],
    )
    data = {"name": "Marta", "x": 200.0, "y": 200.0, "bbox": (150, 150, 250, 250), "zone": "Z", "inside": True}
    assert manager._determine_state(emp, data, []) == "Activo"


def test_determine_state_inactive_with_no_movement(manager):
    emp = _add_employee_with_positions(manager, "Luis", [(100.0, 100.0)] * 10)
    data = {"name": "Luis", "x": 100.0, "y": 100.0, "bbox": (50, 50, 150, 150), "zone": "Z", "inside": True}
    assert manager._determine_state(emp, data, []) == "Inactivo"


def test_determine_state_defaults_to_active_with_few_positions(manager):
    emp = _add_employee_with_positions(manager, "Nuevo", [(100.0, 100.0)])
    data = {"name": "Nuevo", "x": 100.0, "y": 100.0, "bbox": (50, 50, 150, 150), "zone": "Z", "inside": True}
    assert manager._determine_state(emp, data, []) == "Activo"


# ---------------------------------------------------------------------------
# _check_timeouts
# ---------------------------------------------------------------------------

def test_check_timeouts_short_absence_sets_tiempo_fuera(manager, mock_db):
    manager.employees["Ausente"] = {
        "positions": [], "last_seen": time.time() - 20,
        "current_state": "Activo", "last_zone": "Z", "on_lunch": False,
    }
    manager._check_timeouts(time.time(), seen_this_frame=set())
    assert manager.get_state("Ausente") == "Tiempo fuera"


def test_check_timeouts_long_absence_sets_hora_de_comer(manager, mock_db):
    manager.employees["EnComida"] = {
        "positions": [], "last_seen": time.time() - 1900,
        "current_state": "Tiempo fuera", "last_zone": "Z", "on_lunch": False,
    }
    manager._check_timeouts(time.time(), seen_this_frame=set())
    assert manager.get_state("EnComida") == "Hora de comer"
    assert manager.employees["EnComida"]["on_lunch"] is True


def test_check_timeouts_employee_seen_this_frame_is_not_timed_out(manager):
    manager.employees["Presente"] = {
        "positions": [], "last_seen": time.time() - 20,
        "current_state": "Activo", "last_zone": "Z", "on_lunch": False,
    }
    manager._check_timeouts(time.time(), seen_this_frame={"Presente"})
    assert manager.get_state("Presente") == "Activo"


# ---------------------------------------------------------------------------
# _bboxes_intersect
# ---------------------------------------------------------------------------

def test_bboxes_intersect_overlapping(manager):
    assert manager._bboxes_intersect((0, 0, 100, 100), (50, 50, 150, 150)) is True


def test_bboxes_intersect_no_overlap_horizontal(manager):
    assert manager._bboxes_intersect((0, 0, 100, 100), (200, 0, 300, 100)) is False


def test_bboxes_intersect_no_overlap_vertical(manager):
    assert manager._bboxes_intersect((0, 0, 100, 100), (0, 200, 100, 300)) is False


def test_bboxes_intersect_one_inside_other(manager):
    assert manager._bboxes_intersect((0, 0, 200, 200), (50, 50, 100, 100)) is True


def test_bboxes_intersect_identical_boxes(manager):
    assert manager._bboxes_intersect((10, 10, 50, 50), (10, 10, 50, 50)) is True
