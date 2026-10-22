import unittest
import time
import sys
import os

# Adjust sys path prior to import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.main_ui import AppMain
from config.path_utils import ConfigManager
import pytest

# GUI heredada: crea ventanas Tk y carga el modelo YOLO; fuera del hook rápido (SPEC/9 §0.6).
pytestmark = pytest.mark.slow


class TestUINavigation(unittest.TestCase):
    def setUp(self):
        # Garantiza que exista un tenant activo tanto en ejecución aislada como en suite completa
        ConfigManager.set_active_tenant("TestTenant_Navigation")

    def test_navigation_speed(self):
        # Bootstraps the app silently
        app = AppMain()
        app.update() # Forzar el renderizado grafico de Tcl/Tk nativo C++
        
        # Test navigation logic traversing all elements sequentially
        views_to_test = ["Empleados", "Zonas", "Reportes", "Tenant", "Dashboard", "Empleados", "Reportes"]
        
        start_time = time.time()
        for v in views_to_test:
            # Alterna pestañas
            app.view_manager.switch_to(v)
            app.update() # Refresca el marco grafico
            
        elapsed_time = (time.time() - start_time) * 1000 # converting entirely to ms
        
        print(f"\n[BENCHMARK] Tiempo para intercambiar 7 vistas consecutivamente en memoria cache: {elapsed_time:.2f} ms")
        self.assertLess(elapsed_time, 500.0, "FATAL B2B ERROR: El cambio de pestañas excede enormemente los 500ms. La UI lagueara durante el monitoreo Multi-Tenant.")
        
        # Cleanup C++ widget bindings explicitly
        app.destroy()

if __name__ == "__main__":
    unittest.main()
