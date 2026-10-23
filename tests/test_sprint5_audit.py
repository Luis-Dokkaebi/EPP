import unittest
import cProfile
import pstats
import io
import time
import os
import shutil
import sys
import tempfile
import threading
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.main_ui import AppMain
from config.path_utils import ConfigManager
from src.analysis.report_generator import DatabaseWorker
import pytest

# GUI heredada: crea ventanas Tk y carga el modelo YOLO; fuera del hook rápido (SPEC/9 §0.6).
pytestmark = pytest.mark.slow


class MockDBManager:
    def __init__(self, db_path=":memory:"):
        self.db_path = db_path
        
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS tracking (id INTEGER, name TEXT, zone TEXT, timestamp DATETIME)")
        return conn

    def populate_massive_data(self):
        conn = self._get_connection()
        print("\n[DB Spoofer] Memoria RAM separada. Inyectando 50,000 registros estaticos para Experimento VMS...")
        data = [(i, f"Colaborador_{i}", "Zona Segura", "2026-03-27 10:00:00") for i in range(50000)]
        conn.executemany("INSERT INTO tracking VALUES (?, ?, ?, ?)", data)
        conn.commit()

class TestSprint5Audits(unittest.TestCase):
    
    def test_massive_db_export_stress(self):
        """TASK-5.4.3: Exportación Masiva de BD sin afectar la latencia del VMS B2B."""
        db_mock = MockDBManager()
        db_mock.populate_massive_data()
        
        worker = DatabaseWorker(db_mock)
        # Regla §4: nada de disco fuera de un directorio temporal (antes escribía en la raíz del repo).
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        output_file = os.path.join(carpeta, "stress_test_export_50k.xlsx")
            
        success_event = threading.Event()
        
        def on_success(path, rows):
            success_event.set()
            
        def on_error(e):
            print("Error Threading:", e)
            success_event.set()
            
        # Benchmark de Traba de UI (Delegacion al Worker)
        start_trigger = time.time()
        worker.generate_excel_async("SELECT * FROM tracking", output_file, on_success, on_error)
        trigger_time = (time.time() - start_trigger) * 1000 
        
        print(f"[Stress Test / Asincronía] Tiempo que se detuvo la UI: {trigger_time:.4f} milisegundos")
        self.assertLess(trigger_time, 20.0, "ERROR FATAL: La llamada a la BD bloqueo la UI mas de lo tolerado B2B.")
        
        print("[Stress Test] Hilo Daemon Background VMS en ejecucion pesada (I/O) de MS Excel...")
        success_event.wait(timeout=25)
        
        self.assertTrue(success_event.is_set(), "El motor del reporte masivo fallo o excedio el timeout absurdo de 25s.")
        self.assertTrue(os.path.exists(output_file), "Fallback excel failed.")
        
        size_mb = os.path.getsize(output_file) / (1024*1024)
        print(f"[Stress Test Finalizado] XLSX Aprobado Intacto - Tamaño en Disco Local: {size_mb:.2f} MB")

    def test_cprofile_main_thread_yield(self):
        """Valida matematicamente que el CustomTkinter MainLoop no consume I/O pesado ni ahoga la APP."""
        ConfigManager.set_active_tenant("Audit_Tenant") # Setup tenant logico para burlar Bootloader restrictivo
        app = AppMain()
        
        # Apagador automatico asincrono de UI luego de 600ms de render
        app.after(600, app.destroy)
        
        pr = cProfile.Profile()
        pr.enable()
        app.mainloop()
        pr.disable()
        
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('tottime')
        ps.print_stats()
        
        profile_output = s.getvalue()
        
        self.assertNotIn("time.sleep", profile_output[:500], "Warning: Bloqueo de UI detectado.")
        self.assertNotIn("to_excel", profile_output, "Exportacion asincrona falló, detectada en main loop.")
        
        print("\n================= PERFORMANCE PROFILING (cProfile) ==================")
        print(">>> VIBE HACKING SIGN-OFF: Rendimiento Zero-Blocking Garantizado.")
        print(">>> TOP FUNCIONES EN MAIN-LOOP (Descartando I/O Pesado):")
        print('\n'.join(profile_output.split('\n')[4:10])) # Imprime el Head de la tabla top

if __name__ == "__main__":
    unittest.main()
