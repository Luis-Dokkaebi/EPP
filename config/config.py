# --- config/config.py ---
import os
from pathlib import Path

from config.path_utils import ConfigManager, get_resource_path


class VersionNoEncontradaError(RuntimeError):
    """Falta el archivo VERSION o está vacío: la aplicación no sabe qué versión es."""


def leer_version(ruta: Path) -> str:
    """La versión del producto; su única fuente es el archivo VERSION (SPEC/9 §15, 9.3)."""
    if not ruta.is_file():
        raise VersionNoEncontradaError(f"No se encontró el archivo VERSION en {ruta}")
    version = ruta.read_text(encoding="utf-8").strip()
    if not version:
        raise VersionNoEncontradaError(f"El archivo VERSION en {ruta} está vacío")
    return version


VERSION = leer_version(Path(get_resource_path("VERSION")))

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
MODEL_PATH = get_resource_path('yolov8n.pt')
MANIFEST_PATH = get_resource_path('models/manifest.json')
# Motor de detección (SPEC/9 §1.3.6): pasa a "onnx" cuando un modelo ONNX supere la puerta
# de promoción de A-13 (umbrales de D2). El interruptor se elimina al contraer (A-16, D8).
DETECTION_ENGINE = "ultralytics"

# Otros parámetros generales
FRAME_SKIP = 1
CONFIDENCE_THRESHOLD = 0.4
