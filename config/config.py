# --- config/config.py ---
import os
from config.path_utils import get_resource_path, ConfigManager

# --- Versioning ---
VERSION = "2.0.0" 
try:
    version_path = get_resource_path('VERSION')
    if os.path.exists(version_path):
        with open(version_path, 'r') as f:
            VERSION = f.read().strip()
except Exception:
    pass

MODE = 'local'

# Video
LOCAL_CAMERA_INDEX = 0
REMOTE_CAMERA_URL = "rtsp://usuario:contraseña@IP:PUERTO/cam/path"

# Getter based configuration to support B2B Hot-Swapping Multi-Tenant
# No evaluarlas al instante de importacion! El Tenant debe ser seleccionado primero por el Bootloader.
def get_db_path():
    return os.path.join(ConfigManager.get_tenant_path('db'), 'local_tracking.db')

def get_faces_dir():
    return ConfigManager.get_tenant_path('faces')

def get_zonas_file():
    return os.path.join(ConfigManager.get_tenant_path('zonas'), 'zonas_config.json')

def get_snapshots_dir():
    return ConfigManager.get_tenant_path('snapshots')

def get_export_dir():
    return ConfigManager.get_tenant_path('export')

# Read-only resource paths
# Detector de personas y celulares (ADR-001): RF-DETR Nano en ONNX Runtime.
MODEL_PATH = get_resource_path('models/rfdetr/rfdetr-nano-coco-int8.onnx')
MANIFEST_PATH = get_resource_path('models/manifest.json')
# Reconocimiento facial (opencv_zoo): YuNet detecta (MIT) y SFace codifica (Apache-2.0).
FACE_DETECTOR_PATH = get_resource_path('models/rostros/face_detection_yunet_2023mar.onnx')
FACE_RECOGNIZER_PATH = get_resource_path('models/rostros/face_recognition_sface_2021dec.onnx')

# Otros parámetros generales
FRAME_SKIP = 1
CONFIDENCE_THRESHOLD = 0.4
