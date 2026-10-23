import unittest
from unittest.mock import patch, MagicMock
import queue
import threading
import os
import tempfile
import psutil
import sys
import numpy as np

# Agrandar la ruta al codigo
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.tracking.camera_worker import CameraWorker

_FACES_TMP = os.path.join(tempfile.gettempdir(), 'test_faces_cw')
SEGUNDOS_PARA_DETENERSE = 30
CAPACIDAD = 5
FRAMES_DE_MAS = 5

class MockDetector:
    """Doble de DetectorPort: ninguna detección (SPEC/9 §1.3.5)."""

    def detectar(self, frame):
        return []

class TestCameraWorkerLeaks(unittest.TestCase):
    @patch('config.config.get_faces_dir', return_value=_FACES_TMP)
    @patch('src.tracking.camera_worker.cv2.VideoCapture')
    def test_drop_frame_protocol(self, mock_videocapture, _mock_faces):
        # Configure the Mock Camera to stream empty frames really fast
        mock_cap = MagicMock()
        # Create a dummy frame like what a real camera would return
        dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        # La cámara falsa avisa cuando el worker ya intentó encolar más frames de los que caben:
        # la prueba espera ese hecho en lugar de dormir 5 s (CLAUDE.md §4, sin reloj real).
        lecturas = []
        cola_desbordada = threading.Event()

        def leer():
            lecturas.append(1)
            if len(lecturas) > CAPACIDAD + FRAMES_DE_MAS:
                cola_desbordada.set()
            return (True, dummy_frame)

        mock_cap.read.side_effect = leer
        mock_videocapture.return_value = mock_cap

        # Queue limited to 5 frames
        q = queue.Queue(maxsize=CAPACIDAD)
        detector = MockDetector()

        # Instantiate Camera Worker acting un-throttled to flood queue faster (30 ops)
        worker = CameraWorker(camera_id=0, frame_queue=q, detector=detector, fps_limit=30)
        
        process = psutil.Process(os.getpid())
        mem_start = process.memory_info().rss
        
        # Start background worker
        worker.start()
        
        # Nadie consume la cola: el worker debe descartar los frames que no caben.
        self.assertTrue(cola_desbordada.wait(SEGUNDOS_PARA_DETENERSE),
                        "El worker no llegó a leer más frames de los que caben en la cola.")
        
        # Stop background worker and clean up
        worker.stop()
        worker.join(timeout=SEGUNDOS_PARA_DETENERSE)
        # CLAUDE.md §16: todo start() tiene su stop() probado. Un worker vivo seguiría
        # consumiendo CPU en las pruebas siguientes (en la CI de Windows ahogaba al dashboard).
        self.assertFalse(worker.is_alive(), "El worker debe terminar tras stop().")

        mem_end = process.memory_info().rss
        mem_diff_mb = (mem_end - mem_start) / (1024 * 1024)
        
        # Output Validation
        self.assertTrue(q.full(), "La cola deberia llenarse muy rapido y marcar Full.")
        self.assertEqual(q.qsize(), 5, "El limite estricto de la memoria de encolamiento debe respetarse (5 fps max en standby).")
        
        print(f"Memoria (Mbytes) -> Cambio: {mem_diff_mb:.2f} MB")
        self.assertLess(mem_diff_mb, 50, "El Drop Frame Protocol ha fallado. La memoria local se expandio de forma riesgosa.")

if __name__ == '__main__':
    unittest.main()
