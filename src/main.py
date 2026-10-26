# src/main.py

import cv2
import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import sys
from datetime import datetime

# Add the project root directory to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from config import config
except ImportError:
    # Fallback if config module is not found directly
    sys.path.append(os.getcwd())
    from config import config

from src.composition import crear_detector_configurado
from src.tracking.person_tracker import PersonTracker, separar_personas_y_celulares
from src.zones.zone_checker import ZoneChecker
from src.storage.database_manager import DatabaseManager
from src.recognition.face_recognizer import FaceRecognizer
from src.analysis.state_manager import StateManager
from src.tracking.camera_worker import dibujar_epp
import time
from datetime import timedelta

# Antes de que main() cifre o cierre, el despachador termina el aviso en curso (igual que la GUI).
ESPERA_AL_DETENER_AVISOS = timedelta(seconds=10)


def get_bbox_center(xyxy):
    x1, y1, x2, y2 = xyxy
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    return center_x, center_y


def licencia_del_equipo():
    """La licencia DRM del equipo, ya validada; si no es válida no habilita ningún módulo."""
    from src.security.drm import DRMValidator

    licencia = DRMValidator()
    licencia.validate_license()
    return licencia


def modulo_epp_de_la_sucursal(licencia):
    """SPEC/9 §11 (5.4): el mismo módulo de EPP que arma la GUI.

    None si la licencia o el modelo no lo habilitan.
    """
    from src import composicion_epp

    return composicion_epp.crear_integracion_epp_de_la_app(
        composicion_epp.PublicadorEnMemoria(), licencia
    )


def iniciar_avisos_epp(licencia):
    """Con el módulo de EPP en la licencia (D10), los avisos arrancan como en la GUI."""
    from src import composicion_avisos
    from src.composicion_epp import modulo_habilitado

    if not modulo_habilitado(licencia):
        return None
    return composicion_avisos.iniciar_avisos_de_la_sucursal()


def detener_avisos_epp(despachador):
    if despachador is not None:
        despachador.detener(ESPERA_AL_DETENER_AVISOS)


def start_video_stream():
    # CR-01: el modo headless no pasa por el Bootloader, así que debe seleccionar
    # un Tenant antes de resolver rutas tenant-aware (get_db_path / get_zonas_file /
    # get_snapshots_dir). Usar OE_TENANT_ID o "Default".
    from config.path_utils import ConfigManager

    ConfigManager.set_active_tenant(os.environ.get("OE_TENANT_ID", "Default"))

    # Selección de fuente de video
    if config.MODE == "local":
        video_source = config.LOCAL_CAMERA_INDEX
    else:
        video_source = config.REMOTE_CAMERA_URL

    # Use the camera index selected by the user in the GUI (passed via env var), otherwise fallback
    selected_cam = os.environ.get("SELECTED_CAMERA_INDEX")
    if selected_cam is not None:
        sources_to_try = [int(selected_cam)]
    else:
        sources_to_try = [video_source, 0, 1, 2, 3]

    # Remove duplicates while preserving order
    seen = set()
    unique_sources = []
    for s in sources_to_try:
        if s not in seen:
            seen.add(s)
            unique_sources.append(s)
    sources_to_try = unique_sources

    cap = None

    for src in sources_to_try:
        temp_cap = cv2.VideoCapture(src)
        if temp_cap.isOpened():
            ret, frame = temp_cap.read()
            if ret:
                print(f"✅ Cámara iniciada con éxito en el índice/ruta: {src}")
                cap = temp_cap
                break
            else:
                print(f"⚠️ Cámara en origen {src} no devolvió frame. Omitiendo...")
        temp_cap.release()

    if not cap or not cap.isOpened():
        print(
            "❌ Error: No se pudo detectar ninguna cámara (ni local ni externa). Revisar conexiones."
        )
        return

    # Ensure all data directories exist before loading
    # CR-07: usar el getter tenant-aware (ruta canónica Tenants/<ID>/zonas/), no getattr.
    zonas_file = config.get_zonas_file()
    os.makedirs(os.path.dirname(zonas_file), exist_ok=True)
    if not os.path.exists(zonas_file):
        with open(zonas_file, "w") as f:
            f.write("{}")

    # Inicializamos los módulos
    detector = crear_detector_configurado(config.CONFIDENCE_THRESHOLD)
    tracker = PersonTracker()
    zone_checker = ZoneChecker(zones_path=zonas_file)
    db_manager = DatabaseManager(db_path=config.get_db_path())

    # Initialize face recognizer
    face_recognizer = FaceRecognizer()

    # Initialize state manager
    state_manager = StateManager(db_manager)

    # Ensure snapshots dir exists
    # CR-07: usar el getter tenant-aware (ruta canónica Tenants/<ID>/snapshots/), no getattr.
    snapshots_dir = config.get_snapshots_dir()
    os.makedirs(snapshots_dir, exist_ok=True)

    # CR-04: lógica de negocio compartida (tracking + zonas + reconocimiento +
    # persistencia). El MISMO TrackingPipeline lo usa la GUI (CameraWorker) para
    # que ambos pipelines no diverjan. Headless reconoce/escribe cada frame.
    from src.tracking.tracking_pipeline import TrackingPipeline

    licencia = licencia_del_equipo()
    pipeline = TrackingPipeline(
        db=db_manager,
        zone_checker=zone_checker,
        tracker=tracker,
        state_manager=state_manager,
        face_recognizer=face_recognizer,
        snapshots_dir=snapshots_dir,
        db_write_interval=1,
        face_check_interval=1,
        epp=modulo_epp_de_la_sucursal(licencia),
    )
    despachador = iniciar_avisos_epp(licencia)

    print("✅ Sistema iniciado. Presiona 'q' para salir.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_time = time.time()

        # Detección (DetectorPort, SPEC/9 §1.3.5) y separación de personas y celulares
        detecciones = detector.detectar(frame)
        person_detections, phones_data = separar_personas_y_celulares(detecciones)

        # CR-04: toda la lógica (tracking IDs, zonas, reconocimiento, snapshots y
        # persistencia a BD) ocurre en el pipeline compartido; el EPP recibe todas las detecciones.
        track_data = pipeline.process(
            frame, person_detections, phones_data, current_time, detecciones=detecciones
        )

        # Dibujar colores/etiquetas basados en el estado calculado
        for td in track_data:
            x1, y1, x2, y2 = td["bbox"]
            display_name = td["name"]
            current_state = state_manager.get_state(display_name)
            color = state_manager.get_color_for_state(current_state)
            label = f"{display_name} - {current_state}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.imshow("Sistema de Monitoreo Completo", dibujar_epp(frame, track_data))

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    detener_avisos_epp(despachador)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    start_video_stream()
