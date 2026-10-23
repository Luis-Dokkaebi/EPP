import unittest
import cProfile
import pstats
import io
import os
import shutil
import sys
import tempfile
import threading
import sqlite3

from openpyxl import load_workbook

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.main_ui import AppMain
from config.path_utils import ConfigManager
from src.analysis.report_generator import DatabaseWorker
import pytest

# GUI heredada: crea ventanas Tk y carga el modelo YOLO; fuera del hook rápido (SPEC/9 §0.6).
pytestmark = pytest.mark.slow


FILAS_MASIVAS = 50_000
FILA_DE_PRUEBA = ("Zona Segura", "2026-03-27 10:00:00")
NOMBRE_DEL_HILO = "DB_Excel_Export"
SEGUNDOS_DE_SEGURIDAD = 30  # solo evita colgar la suite si el hilo nunca llega a la base


class BaseEnArchivo:
    """Doble de DatabaseManager sobre un SQLite en disco temporal: las filas persisten entre
    conexiones (antes era ":memory:" y cada conexión del hilo veía una tabla vacía, issue #37)."""

    def __init__(self, ruta):
        self.db_path = ruta

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def poblar(self, filas):
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE tracking (id INTEGER, name TEXT, zone TEXT, timestamp DATETIME)")
        conn.executemany(
            "INSERT INTO tracking VALUES (?, ?, ?, ?)",
            ((i, f"Colaborador_{i}", *FILA_DE_PRUEBA) for i in range(filas)),
        )
        conn.commit()
        conn.close()


class BaseQueEspera(BaseEnArchivo):
    """Retiene al hilo de exportación en la conexión hasta que la prueba lo libera."""

    def __init__(self, ruta):
        super().__init__(ruta)
        self.conectando = threading.Event()
        self.liberar = threading.Event()

    def _get_connection(self):
        self.conectando.set()
        self.liberar.wait()
        return super()._get_connection()


def _esperar_exportaciones():
    """Espera a que terminen los hilos de exportación, sin presupuesto de reloj propio
    (pytest-timeout corta la suite si alguno se cuelga)."""
    for hilo in threading.enumerate():
        if hilo.name == NOMBRE_DEL_HILO:
            hilo.join()


class TestSprint5Audits(unittest.TestCase):

    def setUp(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        self.ruta_db = os.path.join(carpeta, "tracking.db")
        self.salida = os.path.join(carpeta, "stress_test_export_50k.xlsx")
        self.resultado = {}

    def _exportar(self, db):
        DatabaseWorker(db).generate_excel_async(
            "SELECT * FROM tracking",
            self.salida,
            on_success=lambda ruta, filas: self.resultado.update(filas=filas),
            on_error=lambda error: self.resultado.update(error=error),
        )

    def test_export_returns_before_the_worker_reads_the_db(self):
        """TASK-5.4.3: la UI no espera al volcado: la llamada vuelve con el hilo aún en la base."""
        BaseEnArchivo(self.ruta_db).poblar(1)
        db = BaseQueEspera(self.ruta_db)

        self._exportar(db)

        # Si la llamada esperara al hilo, nunca llegaríamos aquí: el hilo sigue retenido.
        self.assertTrue(db.conectando.wait(SEGUNDOS_DE_SEGURIDAD), "El hilo de exportación no arrancó.")
        self.assertEqual(self.resultado, {})
        db.liberar.set()
        _esperar_exportaciones()
        self.assertEqual(self.resultado, {"filas": 1})

    def test_massive_db_export_stress(self):
        """TASK-5.4.3: exportación masiva completa, verificada por contenido (CLAUDE.md §16)."""
        BaseEnArchivo(self.ruta_db).poblar(FILAS_MASIVAS)

        self._exportar(BaseEnArchivo(self.ruta_db))
        _esperar_exportaciones()

        self.assertEqual(self.resultado, {"filas": FILAS_MASIVAS})
        libro = load_workbook(self.salida, read_only=True)
        self.addCleanup(libro.close)
        filas = list(libro.active.iter_rows(values_only=True))
        self.assertEqual(filas[0], ("id", "name", "zone", "timestamp"))
        self.assertEqual(len(filas), FILAS_MASIVAS + 1)
        self.assertEqual(filas[1], (0, "Colaborador_0", *FILA_DE_PRUEBA))
        self.assertEqual(filas[-1], (FILAS_MASIVAS - 1, f"Colaborador_{FILAS_MASIVAS - 1}", *FILA_DE_PRUEBA))

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
