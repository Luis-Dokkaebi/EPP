"""
Test: Dashboard Grid Multiplexor (v1.2.2)
Valida que DashboardFrame no mezcle geometry managers pack/grid (TclError fix).
Prueba directa del widget sin dependencias de YOLO, DRM ni cámaras reales.
"""
import unittest
import sys
import os
import queue
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Necesitamos Tk disponible
import customtkinter as ctk
ctk.set_appearance_mode("Dark")

CICLOS_DE_ACTUALIZACION = 3


class TestGridMultiplexor(unittest.TestCase):
    """Prueba unitaria del DashboardFrame aislado (sin AppMain completo)."""

    def setUp(self):
        try:
            self.root = ctk.CTk()
            self.root.withdraw()  # No mostrar ventana
        except Exception as e:
            self.skipTest(f"Tkinter/CustomTkinter no disponible en este entorno: {e}")

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_zero_cameras_uses_grid_not_pack(self):
        """BUGFIX v1.2.2: Con 0 cámaras, el label 'No hay transmisiones' debe usar grid, no pack."""
        from src.gui.dashboard import DashboardFrame
        
        empty_queues = {}
        dashboard = DashboardFrame(self.root, empty_queues)
        dashboard.grid(row=0, column=0, sticky="nsew")
        self.root.update_idletasks()
        
        # Verificar que los hijos usan grid (grid_info no vacio)
        children = dashboard.winfo_children()
        self.assertGreater(len(children), 0, "Debe haber al menos 1 widget hijo (label placeholder)")
        for child in children:
            info = child.grid_info()
            self.assertTrue(len(info) > 0, f"Widget {child} debe estar colocado con grid(), no pack()")

    def test_transition_zero_to_n_cameras_no_tcl_error(self):
        """BUGFIX v1.2.2: Transición de 0 → N cámaras NO debe lanzar TclError."""
        from src.gui.dashboard import DashboardFrame
        
        camera_queues = {}
        dashboard = DashboardFrame(self.root, camera_queues)
        dashboard.grid(row=0, column=0, sticky="nsew")
        self.root.update_idletasks()
        
        # Ahora simular que se agregan cámaras (como hace _start_local_camera)
        camera_queues["Cámara Local"] = queue.Queue(maxsize=10)
        camera_queues["Cámara IP 1"] = queue.Queue(maxsize=10)
        dashboard.camera_queues = camera_queues
        
        # Esto fallaba con TclError antes del fix
        try:
            dashboard.setup_grid()
            self.root.update_idletasks()
        except Exception as e:
            self.fail(f"setup_grid() lanzó excepción al transicionar 0→N cámaras: {e}")
        
        # Verificar que se crearon los labels de video
        self.assertEqual(len(dashboard.video_labels), 2, "Debe haber 2 video labels")
        
        # Verificar que todos usan grid
        for cam_id, lbl in dashboard.video_labels.items():
            info = lbl.grid_info()
            self.assertTrue(len(info) > 0, f"Label de {cam_id} debe estar en grid")

    def test_grid_nxn_layout_correct(self):
        """Verifica que la cuadrícula NxN se calcule correctamente para 4 cámaras (2x2)."""
        from src.gui.dashboard import DashboardFrame
        
        camera_queues = {
            "Cam 1": queue.Queue(maxsize=5),
            "Cam 2": queue.Queue(maxsize=5),
            "Cam 3": queue.Queue(maxsize=5),
            "Cam 4": queue.Queue(maxsize=5),
        }
        dashboard = DashboardFrame(self.root, camera_queues)
        dashboard.grid(row=0, column=0, sticky="nsew")
        self.root.update_idletasks()
        
        self.assertEqual(len(dashboard.video_labels), 4)
        
        # Verificar posiciones grid (2x2)
        positions = []
        for cam_id, lbl in dashboard.video_labels.items():
            info = lbl.grid_info()
            positions.append((int(info['row']), int(info['column'])))
        
        # Debe haber posiciones (0,0), (0,1), (1,0), (1,1)
        expected = {(0, 0), (0, 1), (1, 0), (1, 1)}
        self.assertEqual(set(positions), expected, f"Layout 2x2 incorrecto: {positions}")

    def test_toggle_single_view_and_restore(self):
        """Verifica que toggle_single_view funcione sin mezclar geometry managers."""
        from src.gui.dashboard import DashboardFrame
        
        camera_queues = {
            "Cam A": queue.Queue(maxsize=5),
            "Cam B": queue.Queue(maxsize=5),
        }
        dashboard = DashboardFrame(self.root, camera_queues)
        dashboard.grid(row=0, column=0, sticky="nsew")
        self.root.update_idletasks()
        
        # Expandir vista de "Cam A"
        dashboard.toggle_single_view("Cam A")
        self.root.update_idletasks()
        self.assertTrue(dashboard.is_single_view)
        
        # Restaurar
        dashboard.toggle_single_view("Cam A")
        self.root.update_idletasks()
        self.assertFalse(dashboard.is_single_view)
        
        # Verificar que ambas cámaras están visibles de nuevo en grid
        for cam_id, lbl in dashboard.video_labels.items():
            info = lbl.grid_info()
            self.assertTrue(len(info) > 0, f"Label de {cam_id} debe estar visible en grid tras restaurar")

    def test_frame_consumption_with_mock_producers(self):
        """Cada ciclo de actualización consume la cola y muestra el frame más reciente.

        Determinista (issue #37): antes medía actualizaciones por segundo de reloj real con
        sleep, y en la CI de Windows fallaba según la carga del runner (CLAUDE.md §4).
        """
        from src.gui.dashboard import DashboardFrame

        cola = queue.Queue(maxsize=10)
        dashboard = DashboardFrame(self.root, {"Test Cam": cola})
        dashboard.grid(row=0, column=0, sticky="nsew")
        self.root.update_idletasks()
        etiqueta = dashboard.video_labels["Test Cam"]

        for ciclo in range(CICLOS_DE_ACTUALIZACION):
            atrasado = np.full((48, 64, 3), ciclo, dtype=np.uint8)
            reciente = np.full((48, 64, 3), (ciclo, 100, 200), dtype=np.uint8)
            cola.put_nowait(("Test Cam", atrasado))
            cola.put_nowait(("Test Cam", reciente))

            dashboard.update_frames()

            self.assertTrue(cola.empty(), f"El ciclo {ciclo} debe vaciar la cola")
            mostrado = np.asarray(etiqueta.image.cget("light_image"))
            # El dashboard convierte BGR a RGB: se muestra el frame más reciente, no el atrasado.
            np.testing.assert_array_equal(mostrado, reciente[:, :, ::-1])


if __name__ == "__main__":
    unittest.main()
