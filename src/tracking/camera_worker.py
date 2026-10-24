import cv2
import queue
import threading
import time
import numpy as np
from src.inference.ports import DetectorPort
from src.recognition.face_recognizer import FaceRecognizer
from src.ppe.application.vista_cumplimiento import vista_de
from src.ppe.domain.geometria import Caja
from src.tracking.annotator import AnotadorDeFrames
from src.tracking.overlay_epp import dibujar_cumplimiento
from src.tracking.person_tracker import separar_personas_y_celulares


def dibujar_epp(frame, track_data):
    """Overlay de cumplimiento (SPEC/9 §8.1) de las personas que tienen estado de EPP."""
    personas = [(Caja(*dato['bbox']), vista_de(dato['epp']))
                for dato in track_data if dato.get('epp') is not None]
    return dibujar_cumplimiento(frame, personas) if personas else frame


class CameraWorker(threading.Thread):
    def __init__(self, camera_id: int | str, frame_queue: queue.Queue, detector: DetectorPort,
                 fps_limit: int = 15):
        super().__init__(daemon=True) # El hilo muere al cerrar la app
        self.camera_id = camera_id
        self.frame_queue = frame_queue
        # SPEC/9 §1.3.5: el worker no conoce el motor de IA, solo el puerto de detección.
        self.detector = detector
        self.anotador = AnotadorDeFrames()
        self.fps_limit = fps_limit
        self.running = False
        self._delay = 1.0 / self.fps_limit
        
        # FIX: Usar get_faces_dir() para garantizar la MISMA ruta que usa la UI de registro
        from config.config import get_faces_dir
        faces_dir = get_faces_dir()

        self.face_rec = FaceRecognizer(faces_dir=faces_dir)
        self.frame_counter = 0
        self.last_name = "Unknown"
        self.last_name_time = 0

        # --- CR-04: persistencia de tracking en la GUI ---
        # Antes el CameraWorker SOLO dibujaba cajas y mostraba el nombre: nunca
        # escribía a la BD → reportes vacíos. Ahora reutiliza el TrackingPipeline
        # compartido con main.py (zonas + tracking IDs + asistencia + estados +
        # snapshots). Se crea de forma tolerante a fallos: si faltan dependencias
        # nativas (supervision/shapely) o el Tenant no está montado, el worker
        # sigue mostrando video pero sin persistir (self.pipeline = None).
        self.pipeline = None
        try:
            from config.config import get_db_path, get_zonas_file, get_snapshots_dir
            from src.storage.database_manager import DatabaseManager
            from src.zones.zone_checker import ZoneChecker
            from src.tracking.person_tracker import PersonTracker
            from src.analysis.state_manager import StateManager
            from src.tracking.tracking_pipeline import TrackingPipeline

            self.db = DatabaseManager(db_path=get_db_path())
            self.zone_checker = ZoneChecker(zones_path=get_zonas_file())
            self.tracker = PersonTracker()
            self.state_manager = StateManager(self.db)
            self.pipeline = TrackingPipeline(
                db=self.db, zone_checker=self.zone_checker, tracker=self.tracker,
                state_manager=self.state_manager, face_recognizer=self.face_rec,
                snapshots_dir=get_snapshots_dir(),
                db_write_interval=15, face_check_interval=10,
            )
        except Exception as exc:
            print(f"[CameraWorker][CR-04] Persistencia deshabilitada "
                  f"({type(exc).__name__}: {exc}). El video seguirá mostrándose.")

        # --- TASK-5.2: Verificacion de integridad del modelo AI (Anti-Tamper) ---
        # Si el yolov8n.pt en disco fue reemplazado por un modelo falso/backdoor,
        # el hash SHA-256 no coincide y el tracking se deshabilita (SPEC 5.2 DoD).
        self.model_verified = True
        try:
            from config.config import MODEL_PATH
            from src.models.model_verifier import verify_model
            self.model_verified = verify_model(MODEL_PATH)
            if not self.model_verified:
                print(f"[VMS][SECURITY] Modelo AI manipulado en {MODEL_PATH}. "
                      f"Inferencia DESHABILITADA para cámara {self.camera_id}.")
        except FileNotFoundError as exc:
            # Modelo ausente: no podemos verificar -> deshabilitar por seguridad
            self.model_verified = False
            print(f"[VMS][SECURITY] No se pudo verificar el modelo AI: {exc}")
        print(f"[CameraWorker] FaceRecognizer cargado. faces_dir={faces_dir}, "
              f"encodings={len(self.face_rec.known_face_names)} rostro(s): {self.face_rec.known_face_names}")

    def run(self):
        # TASK-5.2 DoD: si el modelo fue manipulado, abortar el tracking de inmediato.
        if not self.model_verified:
            print(f"[VMS][SECURITY] Cámara {self.camera_id} no inicia: integridad del modelo AI inválida.")
            return
        self.running = True
        if isinstance(self.camera_id, int):
            cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.camera_id)
        else:
            cap = cv2.VideoCapture(self.camera_id)
        
        # Fallback de autodescubrimiento B2B
        if not cap.isOpened():
            print(f"[VMS] Cámara {self.camera_id} falló. Intentando autodescubrimiento...")
            for idx in [0, 1, 2]:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    print(f"[VMS] Cámara {idx} de respaldo conectada exitosamente.")
                    self.camera_id = idx
                    break
                    
        # Optimizacion OpenCV B2B: Forzar resolucion (opcional)
        # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        while self.running:
            start_time = time.time()
            ret, frame = cap.read()
            
            if not ret or frame is None or frame.size == 0:
                # Log de reconexion en entorno Enterprise (ej. RTSP perdido)
                time.sleep(2.0)
                if isinstance(self.camera_id, int):
                    cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        cap = cv2.VideoCapture(self.camera_id)
                else:
                    cap = cv2.VideoCapture(self.camera_id)
                continue

            detecciones = self.detector.detectar(frame)
            annotated_frame = self.anotador.anotar(frame, detecciones)

            self.frame_counter += 1

            # --- HOT-RELOAD: Detectar nuevos empleados registrados cada ~60 frames (~4s) ---
            if self.frame_counter % 60 == 0:
                self.face_rec.check_reload()

            # --- CR-04: PERSISTENCIA + reconocimiento vía pipeline compartido ---
            # El pipeline trackea IDs, evalúa zonas, reconoce rostros (skip-frame) y
            # escribe a la BD (tracking/snapshots/asistencia/estados). Envuelto en
            # try/except para que un fallo de persistencia NUNCA congele el video.
            if self.pipeline is not None:
                try:
                    person_detections, phones_data = separar_personas_y_celulares(detecciones)
                    track_data = self.pipeline.process(
                        frame, person_detections, phones_data, time.time(),
                        detecciones=detecciones)
                    annotated_frame = dibujar_epp(annotated_frame, track_data)

                    # Banner biométrico en pantalla con el nombre reconocido
                    known = [td['name'] for td in track_data if td['name'] != "Unknown"]
                    if known:
                        self.last_name = known[0]
                        self.last_name_time = time.time()
                except Exception as exc:
                    print(f"[CameraWorker][CR-04] Error de persistencia "
                          f"({type(exc).__name__}). Video intacto.")

            # Dejar el nombre visible en la pantalla por un momento
            if self.last_name != "Unknown" and (time.time() - self.last_name_time) < 3.0:
                label = f"BIOMETRIA VMS: {self.last_name}"
                cv2.rectangle(annotated_frame, (10, 10), (500, 60), (0, 0, 0), -1)
                cv2.putText(annotated_frame, label, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)

            # --- DROP FRAME PROTOCOL (Anti-Memory Leak) ---
            try:
                # Intenta encolar sin bloquear. Si esta llena (UI retardada), entra al except
                self.frame_queue.put_nowait((self.camera_id, annotated_frame))
            except queue.Full:
                # Se descarta este frame para que la memoria no colapse
                pass 
                
            # Limitar FPS para ahorrar CPU (Artificial Throttle)
            elapsed_time = time.time() - start_time
            time_to_wait = self._delay - elapsed_time
            if time_to_wait > 0:
                time.sleep(time_to_wait)
                
        cap.release()

    def conectar_epp(self, modulo_epp):
        """SPEC/9 §5.1: el módulo de EPP evalúa sobre el pipeline de esta cámara.

        Sin pipeline (sin sucursal montada) no hay personas ni zonas que evaluar.
        """
        if self.pipeline is not None:
            self.pipeline.epp = modulo_epp

    def stop(self):
        self.running = False
