# src/tracking/tracking_pipeline.py
"""
Pipeline de negocio COMPARTIDO (CR-04).

Antes existían dos pipelines paralelos y divergentes:
  - Headless (`src/main.py`): detectaba zonas, trackeaba IDs, reconocía rostros y
    PERSISTÍA a la BD (tracking / snapshots / asistencia / estados).
  - GUI de producción (`src/tracking/camera_worker.py`): SOLO dibujaba cajas y
    mostraba el nombre en pantalla. Nunca llamaba a ZoneChecker / PersonTracker /
    StateManager ni a DatabaseManager → la tabla `tracking` jamás recibía un INSERT
    y todos los reportes salían vacíos (fallo silencioso, CR-04).

Esta clase centraliza la lógica de negocio (tracking + zonas + reconocimiento +
persistencia) para que AMBOS puntos de entrada la invoquen y no vuelvan a
desincronizarse.
"""
import os
import time
from datetime import datetime

from src.tracking.integracion_epp import personas_en_escena


def get_bbox_center(xyxy):
    x1, y1, x2, y2 = xyxy
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


class TrackingPipeline:
    def __init__(self, db, zone_checker, tracker, state_manager,
                 face_recognizer=None, snapshots_dir=None,
                 db_write_interval=15, face_check_interval=10, epp=None):
        self.db = db
        self.zone_checker = zone_checker
        self.tracker = tracker
        self.state_manager = state_manager
        self.face_recognizer = face_recognizer
        self.snapshots_dir = snapshots_dir
        if snapshots_dir:
            os.makedirs(snapshots_dir, exist_ok=True)

        # Cadencias (CR-04 paso 3): NO insertar en cada frame — a 15 fps × N cámaras
        # eso satura SQLite. Las inserciones de posición (`tracking`) se escriben
        # cada `db_write_interval` frames; los snapshots de ENTRADA a zona son
        # por-evento (siempre, sin throttle). El reconocimiento facial (costoso,
        # ~100-200ms en CPU) corre solo cada `face_check_interval` frames
        # (Skip-Frame Biométrica, 2_PLANNING §2.4.1).
        self.db_write_interval = max(1, int(db_write_interval))
        self.face_check_interval = max(1, int(face_check_interval))

        # SPEC/9 §5.1: módulo de EPP opcional (licencia y modelo, D10). Recibe las personas, sus
        # zonas y las detecciones que ya calculó el pipeline; no repite el cálculo de zonas.
        self.epp = epp

        self.zone_state = {}          # {track_id: {zone_name: bool}}
        self.track_id_to_name = {}    # {track_id: nombre}
        self.frame_counter = 0

    def process(self, frame, person_detections, phones_data, current_time=None,
                detecciones=()):
        """
        Ejecuta la lógica de negocio sobre un frame y persiste los resultados.

        Args:
            frame: numpy array BGR (para snapshot / reconocimiento facial).
            person_detections: detecciones de personas (supervision Detections)
                que se pasan a `tracker.update()`.
            phones_data: lista de bboxes de celulares [(x1,y1,x2,y2), ...].
            current_time: epoch float (default: time.time()).
            detecciones: todas las Deteccion del frame (EPP y anclas) para el módulo de EPP.

        Returns:
            track_data: lista de dicts {name, x, y, bbox, zone, inside} para que el
            caller dibuje etiquetas/estado si lo desea.
        """
        if current_time is None:
            current_time = time.time()
        self.frame_counter += 1
        do_db_write = (self.frame_counter % self.db_write_interval == 0)
        do_face_check = (self.frame_counter % self.face_check_interval == 0)

        tracked = self.tracker.update(person_detections)
        track_data = []

        if getattr(tracked, 'tracker_id', None) is not None:
            for xyxy, track_id in zip(tracked.xyxy, tracked.tracker_id):
                track_id = int(track_id)
                x1, y1, x2, y2 = map(int, xyxy)
                cx, cy = get_bbox_center(xyxy)

                # --- Reconocimiento facial (Skip-Frame Biométrica) ---
                current_name = self.track_id_to_name.get(track_id, "Unknown")
                if (current_name == "Unknown" and do_face_check
                        and self.face_recognizer is not None):
                    try:
                        recognized = self.face_recognizer.recognize_face(
                            frame, bbox=(x1, y1, x2, y2))
                    except Exception:
                        recognized = "Unknown"
                    if recognized and recognized != "Unknown":
                        self.track_id_to_name[track_id] = recognized
                display_name = self.track_id_to_name.get(track_id, "Unknown")

                # --- Zonas (Shapely) ---
                zones = self.zone_checker.check(cx, cy)
                current_zone = "Fuera de zona"
                inside_flag = False
                for z_name, inside in zones.items():
                    if inside:
                        current_zone = z_name
                        inside_flag = True
                        break

                track_data.append({
                    'name': display_name, 'x': cx, 'y': cy,
                    'bbox': (x1, y1, x2, y2),
                    'zone': current_zone, 'inside': inside_flag,
                    # SPEC/9 §5.1: el EPP necesita el track y todas las zonas donde está.
                    'track_id': track_id,
                    'zones': frozenset(nombre for nombre, dentro in zones.items() if dentro),
                })

                if track_id not in self.zone_state:
                    self.zone_state[track_id] = {}

                for zone_name, inside in zones.items():
                    inside_zone = int(inside)
                    was_inside = self.zone_state[track_id].get(zone_name, False)

                    # Evento de ENTRADA a zona → snapshot (siempre, por-evento)
                    if inside_zone and not was_inside:
                        self._save_snapshot_event(frame, track_id, display_name, zone_name)

                    self.zone_state[track_id][zone_name] = bool(inside_zone)

                    # Registro de posición (throttled)
                    if do_db_write:
                        self.db.insert_record(
                            track_id=track_id, x=cx, y=cy,
                            zone=zone_name, inside_zone=inside_zone,
                            employee_name=display_name,
                        )

        self._evaluar_epp(frame, track_data, detecciones)

        # StateManager corre cada frame procesado (maneja su propia temporización
        # de asistencia / estados internamente).
        self.state_manager.process_frame(current_time, track_data, phones_data)
        return track_data

    def _evaluar_epp(self, frame, track_data, detecciones):
        """Agrega a cada persona su estado de EPP ('epp'), o None si no hay módulo o estado."""
        estados = {}
        if self.epp is not None:
            estados = self.epp.evaluar(frame, personas_en_escena(track_data), list(detecciones))
        for dato in track_data:
            dato['epp'] = estados.get(dato['track_id'])

    def _save_snapshot_event(self, frame, track_id, display_name, zone_name):
        if not self.snapshots_dir:
            return
        try:
            import cv2
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{track_id}_{display_name}_{zone_name}_{ts}.jpg"
            filepath = os.path.join(self.snapshots_dir, filename)
            cv2.imwrite(filepath, frame)
            self.db.insert_snapshot(track_id, zone_name, filepath,
                                    employee_name=display_name)
        except Exception as e:
            print(f"[TrackingPipeline] Error guardando snapshot: {type(e).__name__}: {e}")
