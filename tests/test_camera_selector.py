"""
Test: Camera Enumerator (v1.3.0)
Valida la enumeración de cámaras disponibles y la función de selección manual.
"""
import unittest
import sys
import os
import threading
import pytest

# GUI heredada: crea ventanas Tk y carga el modelo YOLO; fuera del hook rápido (SPEC/9 §0.6).
pytestmark = pytest.mark.slow


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestCameraEnumerator(unittest.TestCase):
    """Pruebas del módulo de enumeración de cámaras."""

    def test_enumerate_returns_list(self):
        """enumerate_cameras debe retornar una lista (vacía o con cámaras)."""
        from src.acquisition.camera_enumerator import enumerate_cameras
        result = enumerate_cameras(max_index=3)
        self.assertIsInstance(result, list)

    def test_camera_dict_structure(self):
        """Si se detecta una cámara, debe tener las claves esperadas."""
        from src.acquisition.camera_enumerator import enumerate_cameras
        result = enumerate_cameras(max_index=3)
        if result:  # Solo si hay cámaras disponibles en este equipo
            cam = result[0]
            required_keys = {"index", "name", "width", "height", "backend", "label"}
            self.assertTrue(required_keys.issubset(cam.keys()),
                            f"Faltan claves: {required_keys - cam.keys()}")
            self.assertIsInstance(cam["index"], int)
            self.assertGreater(cam["width"], 0)
            self.assertGreater(cam["height"], 0)

    def test_async_enumeration_calls_callback(self):
        """enumerate_cameras_async debe llamar al callback con la lista de cámaras."""
        from src.acquisition.camera_enumerator import enumerate_cameras_async
        
        result_holder = {"cameras": None, "called": False}
        event = threading.Event()
        
        def callback(cameras):
            result_holder["cameras"] = cameras
            result_holder["called"] = True
            event.set()
        
        t = enumerate_cameras_async(callback, max_index=3)
        event.wait(timeout=15)
        
        self.assertTrue(result_holder["called"], "Callback no fue invocado dentro del timeout")
        self.assertIsInstance(result_holder["cameras"], list)

    def test_label_format(self):
        """Las etiquetas deben incluir resolución y backend."""
        from src.acquisition.camera_enumerator import enumerate_cameras
        result = enumerate_cameras(max_index=3)
        for cam in result:
            label = cam["label"]
            self.assertIn("Cámara", label)
            self.assertIn("x", label)  # WxH
            self.assertIn("(", label)
            self.assertIn(")", label)


class TestCameraSelectorUI(unittest.TestCase):
    """Pruebas del selector de cámara integrado en el sidebar."""

    def test_switch_camera_workflow(self):
        """Valida que _switch_camera no lance excepciones."""
        import customtkinter as ctk
        ctk.set_appearance_mode("Dark")
        
        root = ctk.CTk()
        root.withdraw()
        
        try:
            from src.gui.dashboard import DashboardFrame
            import queue
            
            # Simular estado mínimo de AppMain sin cargar YOLO
            camera_queues = {}
            dashboard = DashboardFrame(root, camera_queues)
            dashboard.grid(row=0, column=0)
            root.update_idletasks()
            
            # Verificar que setup_grid funciona con 0 y luego con 1 cámara
            self.assertEqual(len(dashboard.video_labels), 0)
            
            camera_queues["Test"] = queue.Queue(maxsize=5)
            dashboard.camera_queues = camera_queues
            dashboard.setup_grid()
            root.update_idletasks()
            
            self.assertEqual(len(dashboard.video_labels), 1)
            
            # Simular switch: limpiar y recrear
            camera_queues.clear()
            dashboard.camera_queues = camera_queues
            dashboard.setup_grid()
            root.update_idletasks()
            
            self.assertEqual(len(dashboard.video_labels), 0)
            
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
