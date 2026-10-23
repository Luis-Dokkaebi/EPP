import cv2
import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

try:
    from config.config import ZONAS_FILE as _DEFAULT_ZONAS
except ImportError:
    _DEFAULT_ZONAS = "data/zonas/zonas.json"

from src.zones.edicion_zonas import guardar_poligono

class ZoneEditor:
    def __init__(self, output_path=None):
        if output_path is None:
            self.output_path = _DEFAULT_ZONAS
        else:
            self.output_path = output_path
        # Determina la raíz del proyecto (used only for loading reference images)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.abspath(os.path.join(script_dir, "../.."))
        self.points = []

    def click_event(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"🟢 Punto agregado: ({x}, {y})")
            self.points.append((x, y))

    def save_zone(self, zone_name):
        # v2 conservando el EPP exigido de la zona (SPEC/9 §8.3); valida el nombre (TASK-5.3).
        guardar_poligono(Path(self.output_path), zone_name, self.points)

        print(f"✅ Zona '{zone_name}' guardada en {self.output_path}")

    def run(self, image_path, zone_name):
        absolute_image_path = os.path.abspath(os.path.join(self.project_root, image_path))
        print("📂 Ruta absoluta resuelta:", absolute_image_path)
        print("🧭 Cargando imagen desde:", absolute_image_path)

        image = cv2.imread(absolute_image_path)
        if image is None:
            print("❌ La imagen no se pudo cargar. Verifica la ruta o el archivo.")
            return
        print("✅ Imagen cargada correctamente. Tamaño:", image.shape)

        clone = image.copy()
        cv2.namedWindow("Seleccione puntos (presione 's' para guardar)", cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("Seleccione puntos (presione 's' para guardar)", self.click_event)

        while True:
            for point in self.points:
                cv2.circle(image, point, 3, (0, 255, 0), -1)

            cv2.imshow("Seleccione puntos (presione 's' para guardar)", image)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("s"):
                break

            image = clone.copy()

        cv2.destroyAllWindows()
        self.save_zone(zone_name)

# 💖 Bloque de ejecución directa
if __name__ == "__main__":
    editor = ZoneEditor()
    editor.run("data/zonas/frame_referencia.jpg", "Zona")
