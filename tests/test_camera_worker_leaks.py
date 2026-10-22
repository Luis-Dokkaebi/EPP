import unittest
from unittest.mock import patch, MagicMock
import queue
import time
import os
import tempfile
import psutil
import sys
import numpy as np

# Agrandar la ruta al codigo
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.tracking.camera_worker import CameraWorker

_FACES_TMP = os.path.join(tempfile.gettempdir(), 'test_faces_cw')

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
        mock_cap.read.return_value = (True, dummy_frame)
        mock_videocapture.return_value = mock_cap

        # Queue limited to 5 frames
        q = queue.Queue(maxsize=5)
        detector = MockDetector()

        # Instantiate Camera Worker acting un-throttled to flood queue faster (30 ops)
        worker = CameraWorker(camera_id=0, frame_queue=q, detector=detector, fps_limit=30)
        
        process = psutil.Process(os.getpid())
        mem_start = process.memory_info().rss
        
        # Start background worker
        worker.start()
        
        # Wait 5 seconds, ignoring the queue output effectively filling it and leaking frames if bugged.
        print("\nSaturando la cola compartida (esperando 5 segundos)..")
        time.sleep(5)
        
        # Stop background worker and clean up
        worker.stop()
        worker.join(timeout=2)

        mem_end = process.memory_info().rss
        mem_diff_mb = (mem_end - mem_start) / (1024 * 1024)
        
        # Output Validation
        self.assertTrue(q.full(), "La cola deberia llenarse muy rapido y marcar Full.")
        self.assertEqual(q.qsize(), 5, "El limite estricto de la memoria de encolamiento debe respetarse (5 fps max en standby).")
        
        print(f"Memoria (Mbytes) -> Cambio: {mem_diff_mb:.2f} MB")
        self.assertLess(mem_diff_mb, 50, "El Drop Frame Protocol ha fallado. La memoria local se expandio de forma riesgosa.")

if __name__ == '__main__':
    unittest.main()
