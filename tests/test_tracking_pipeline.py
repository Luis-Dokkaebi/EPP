"""
Regresión CR-04: el TrackingPipeline compartido DEBE PERSISTIR los datos de tracking.

Antes de CR-04 el worker de la GUI nunca escribía a la BD, así que los reportes
salían siempre vacíos. Estas pruebas ejercitan el pipeline con dobles ligeros
(sin cv2/torch/supervision) más el DatabaseManager + StateManager reales para
demostrar que las filas realmente aterrizan en SQLite.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pytest
from src.tracking.tracking_pipeline import TrackingPipeline
from src.storage.database_manager import DatabaseManager
from src.analysis.state_manager import StateManager
from src.ppe.application.evaluar_cumplimiento import PersonaEnEscena
from src.ppe.domain.geometria import Caja


class FakeTracked:
    def __init__(self, boxes, ids):
        self.xyxy = boxes
        self.tracker_id = ids


class FakeTracker:
    """Devuelve una detección trackeada fija, sin importar la entrada."""

    def __init__(self, boxes, ids):
        self._tracked = FakeTracked(boxes, ids)

    def update(self, person_detections):
        return self._tracked


class FakeZoneChecker:
    def __init__(self, result):
        self._result = result

    def check(self, x, y):
        return dict(self._result)


class FakeFaceRecognizer:
    def __init__(self, name="Alice"):
        self._name = name

    def recognize_face(self, frame, bbox=None):
        return self._name


@pytest.fixture
def db(tmp_path):
    return DatabaseManager(db_path=str(tmp_path / "db" / "local_tracking.db"))


def _make_pipeline(db, zones, face_name=None, **kw):
    tracker = FakeTracker(boxes=[(10, 20, 110, 220)], ids=[1])
    zc = FakeZoneChecker(zones)
    sm = StateManager(db)
    fr = FakeFaceRecognizer(face_name) if face_name else None
    return TrackingPipeline(
        db=db,
        zone_checker=zc,
        tracker=tracker,
        state_manager=sm,
        face_recognizer=fr,
        snapshots_dir=None,
        **kw,
    )


def test_pipeline_persists_tracking_rows(db):
    """Una persona dentro de una zona configurada debe producir filas en la BD."""
    pipe = _make_pipeline(
        db, {"ZonaA": True}, face_name="Alice", db_write_interval=1, face_check_interval=1
    )
    frame = object()  # nunca se toca (snapshots_dir=None, sin ruta de cv2)
    for _ in range(3):
        pipe.process(frame, person_detections=None, phones_data=[])

    rows = db.get_all_records()
    assert len(rows) == 3, f"se esperaban 3 filas de tracking, se obtuvieron {len(rows)}"


def test_pipeline_records_attendance_for_recognized_employee(db):
    """El cableado con StateManager debe registrar asistencia del empleado reconocido."""
    pipe = _make_pipeline(
        db, {"ZonaA": True}, face_name="Bob", db_write_interval=1, face_check_interval=1
    )
    pipe.process(object(), None, [])
    assert "Bob" in db.get_unique_employees()


def test_por_omision_escribe_cada_15_frames_y_reconoce_cada_10(db):
    pipe = _make_pipeline(db, {"ZonaA": True})

    assert (pipe.db_write_interval, pipe.face_check_interval) == (15, 10)


def test_db_write_throttle(db):
    """Con db_write_interval=15, solo cada 15.º frame escribe una fila de tracking."""
    pipe = _make_pipeline(
        db, {"ZonaA": True}, face_name="Alice", db_write_interval=15, face_check_interval=10
    )
    for _ in range(30):
        pipe.process(object(), None, [])
    # los frames 15 y 30 escriben → 2 filas
    assert len(db.get_all_records()) == 2


def test_track_data_returned_for_drawing(db):
    pipe = _make_pipeline(
        db, {"ZonaA": True}, face_name="Alice", db_write_interval=1, face_check_interval=1
    )
    td = pipe.process(object(), None, [])
    assert len(td) == 1
    assert td[0]["name"] == "Alice"
    assert td[0]["inside"] is True
    assert td[0]["bbox"] == (10, 20, 110, 220)


def test_no_zone_no_crash(db):
    """Sin zonas configuradas, el pipeline no debe romperse (sin filas, sin error)."""
    pipe = _make_pipeline(db, {}, face_name="Alice", db_write_interval=1, face_check_interval=1)
    td = pipe.process(object(), None, [])
    assert len(td) == 1
    assert db.get_all_records() == []


def test_track_data_includes_track_id_and_every_zone_inside(db):
    """El EPP (SPEC/9 §5.1) necesita el track_id y todas las zonas donde está la persona."""
    zonas = {"ZonaA": True, "ZonaB": False, "ZonaC": True}
    pipe = _make_pipeline(db, zonas, face_name="Alice", db_write_interval=1, face_check_interval=1)
    td = pipe.process(object(), None, [])
    assert (td[0]["track_id"], td[0]["zones"]) == (1, frozenset({"ZonaA", "ZonaC"}))


# --- SPEC/9 §5.1: módulo de EPP opcional sobre lo que ya calculó el pipeline ---


class EvaluadorEPPFalso:
    """Anota cada llamada y devuelve un estado fijo para el track 1."""

    def __init__(self, estados):
        self.llamadas = []
        self._estados = estados

    def evaluar(self, frame, personas, detecciones):
        self.llamadas.append((frame, list(personas), list(detecciones)))
        return dict(self._estados)


def test_sin_modulo_de_epp_el_track_data_no_trae_estado(db):
    pipe = _make_pipeline(db, {"ZonaA": True}, face_name="Alice")

    td = pipe.process(object(), None, [])

    assert td[0]["epp"] is None


def test_el_modulo_de_epp_recibe_personas_zonas_y_detecciones_del_frame(db):
    epp = EvaluadorEPPFalso({1: "estado-del-track-1"})
    pipe = _make_pipeline(
        db, {"ZonaA": True, "ZonaB": False}, face_name="Alice", face_check_interval=1, epp=epp
    )
    frame, detecciones = object(), ["casco", "cabeza"]

    td = pipe.process(frame, None, [], detecciones=detecciones)

    (llamada,) = epp.llamadas
    assert llamada == (
        frame,
        [PersonaEnEscena(1, Caja(10, 20, 110, 220), frozenset({"ZonaA"}), "Alice")],
        ["casco", "cabeza"],
    )
    assert td[0]["epp"] == "estado-del-track-1"


def test_una_persona_sin_estado_de_epp_queda_sin_estado(db):
    epp = EvaluadorEPPFalso({})
    pipe = _make_pipeline(db, {"ZonaA": True}, face_name=None, epp=epp)

    td = pipe.process(object(), None, [])

    assert td[0]["epp"] is None
    assert epp.llamadas[0][1][0].nombre is None
