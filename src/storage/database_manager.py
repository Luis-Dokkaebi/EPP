# src/storage/database_manager.py

import sqlite3
import os
from datetime import datetime

# Whitelist de tablas que almacenan employee_name — nunca deben provenir de input externo.
# Definida aquí como constante de módulo para evitar que futuros cambios introduzcan
# inyección SQL en anonymize_employee (OWASP A03).
_EMPLOYEE_NAME_TABLES = ('tracking', 'snapshots', 'daily_attendance', 'workday_states')

class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'OficinaEficiencia', 'data')
            self.db_path = os.path.join(data_dir, 'db', 'local_tracking.db')
        else:
            self.db_path = db_path
        self._create_table()

    def _get_connection(self):
        """
        Conexion central a SQLite usada por reportes y por el DatabaseWorker
        asincrono (src/analysis/report_generator.py).

        Aplica las mitigaciones de concurrencia del Riesgo 4 (2_PLANNING):
        WAL + synchronous=NORMAL + busy_timeout para tolerar lecturas pesadas
        (export a Excel) simultaneas con inserciones del hilo productor.
        """
        # timeout=30.0 ya fija el busy_timeout de SQLite en 30 000 ms.
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except sqlite3.DatabaseError:
            pass
        return conn

    def _create_table(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Riesgo 4 (2_PLANNING): _get_connection deja la BD en WAL, que persiste como propiedad
        # del archivo y permite lectura/escritura concurrente sin "database is locked".
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        track_id INTEGER,
                        timestamp TEXT,
                        x REAL,
                        y REAL,
                        zone TEXT,
                        inside_zone INTEGER
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        track_id INTEGER,
                        timestamp TEXT,
                        zone TEXT,
                        snapshot_path TEXT
                    )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS daily_attendance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employee_name TEXT,
                        date TEXT,
                        arrival_time TEXT,
                        departure_time TEXT
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS workday_states (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employee_name TEXT,
                        timestamp TEXT,
                        state TEXT
                    )''')

        c.execute('''CREATE TABLE IF NOT EXISTS employees (
                        employee_name TEXT PRIMARY KEY,
                        department TEXT,
                        position TEXT,
                        shift TEXT,
                        registration_date TEXT
                    )''')
        
        # Check for employee_name column in snapshots
        c.execute("PRAGMA table_info(snapshots)")
        columns = [info[1] for info in c.fetchall()]
        if 'employee_name' not in columns:
            print("Adding employee_name column to snapshots table...")
            c.execute("ALTER TABLE snapshots ADD COLUMN employee_name TEXT")

        # Check for employee_name column in tracking
        c.execute("PRAGMA table_info(tracking)")
        tracking_cols = [info[1] for info in c.fetchall()]
        if 'employee_name' not in tracking_cols:
            print("Adding employee_name column to tracking table...")
            c.execute("ALTER TABLE tracking ADD COLUMN employee_name TEXT")

        conn.commit()
        conn.close()

    def insert_record(self, track_id, x, y, zone, inside_zone, employee_name=None):
        conn = self._get_connection()
        c = conn.cursor()
        timestamp = datetime.now().isoformat()
        c.execute("INSERT INTO tracking (track_id, timestamp, x, y, zone, inside_zone, employee_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (track_id, timestamp, x, y, zone, inside_zone, employee_name))
        conn.commit()
        conn.close()

    def insert_snapshot(self, track_id, zone, snapshot_path, employee_name=None):
        conn = self._get_connection()
        c = conn.cursor()
        timestamp = datetime.now().isoformat()
        c.execute("INSERT INTO snapshots (track_id, timestamp, zone, snapshot_path, employee_name) VALUES (?, ?, ?, ?, ?)",
                  (track_id, timestamp, zone, snapshot_path, employee_name))
        conn.commit()
        conn.close()

    def get_all_records(self):
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM tracking")
        rows = c.fetchall()
        conn.close()
        return rows

    def insert_state(self, employee_name, state):
        conn = self._get_connection()
        c = conn.cursor()
        timestamp = datetime.now().isoformat()
        c.execute("INSERT INTO workday_states (employee_name, timestamp, state) VALUES (?, ?, ?)",
                  (employee_name, timestamp, state))
        conn.commit()
        conn.close()

    def update_attendance(self, employee_name):
        conn = self._get_connection()
        c = conn.cursor()
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        # Check if record exists for today
        c.execute("SELECT id FROM daily_attendance WHERE employee_name = ? AND date = ?", (employee_name, date_str))
        row = c.fetchone()

        if row:
            # Update departure time
            c.execute("UPDATE daily_attendance SET departure_time = ? WHERE id = ?", (time_str, row[0]))
        else:
            # Insert new record (first seen today)
            c.execute("INSERT INTO daily_attendance (employee_name, date, arrival_time, departure_time) VALUES (?, ?, ?, ?)",
                      (employee_name, date_str, time_str, time_str))
        
        conn.commit()
        conn.close()

    def employee_exists(self, name):
        """Verifica si un empleado ya existe (case-insensitive)."""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("SELECT 1 FROM employees WHERE LOWER(employee_name) = LOWER(?)", (name,))
        exists = c.fetchone() is not None
        conn.close()
        return exists

    def save_employee_profile(self, name, department='', position='', shift=''):
        """Guarda o actualiza el perfil organizacional del empleado."""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO employees (employee_name, department, position, shift, registration_date)
                     VALUES (?, ?, ?, ?, ?)""",
                  (name, department, position, shift, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_all_employee_names(self):
        """Devuelve los nombres de la tabla employees."""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("SELECT employee_name FROM employees ORDER BY employee_name ASC")
        rows = c.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def get_unique_employees(self):
        """Devuelve una lista de nombres de empleados únicos registrados."""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT employee_name FROM daily_attendance WHERE employee_name IS NOT NULL AND employee_name != ''")
        rows = c.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def get_attendance_report(self, start_date, end_date, employee_name_filter=None):
        """
        Obtiene el reporte de asistencia por rango de fechas y filtro opcional de empleado.
        Retorna: Lista de tuplas (empleado, fecha, hora_llegada, hora_salida, horas_totales_str)
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        query = '''
            SELECT employee_name, date, arrival_time, departure_time 
            FROM daily_attendance 
            WHERE date BETWEEN ? AND ? 
        '''
        params = [start_date, end_date]
        
        if employee_name_filter and employee_name_filter != "Todos":
            query += " AND employee_name = ?"
            params.append(employee_name_filter)
            
        query += " ORDER BY date DESC, employee_name ASC"
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        # Procesamiento para calcular horas totales
        report_data = []
        for row in rows:
            emp_name, date_str, arrival, departure = row
            total_hours_str = "0.00"
            if arrival and departure:
                try:
                    fmt = "%H:%M:%S"
                    t1 = datetime.strptime(arrival, fmt)
                    t2 = datetime.strptime(departure, fmt)
                    delta = t2 - t1
                    total_seconds = delta.total_seconds()
                    # Si salió al día siguiente (turno de noche)
                    if total_seconds < 0:
                        total_seconds += 24 * 3600
                    hours = total_seconds / 3600
                    total_hours_str = f"{hours:.2f}"
                except ValueError:
                    pass
            report_data.append((emp_name, date_str, arrival, departure, total_hours_str))
            
        return report_data

    def get_efficiency_report(self, start_date, end_date, employee_name_filter=None):
        """
        Obtiene el reporte de eficiencia calculando tiempos efectivos e inactivos.
        Retorna: Lista de tuplas (empleado, fecha, tiempo_total_str, tiempo_activo_str, eficiencia_str)
        """
        conn = self._get_connection()
        # Queremos obtener la fecha separada del timestamp
        query = '''
            SELECT employee_name, date(timestamp) as r_date, timestamp, inside_zone 
            FROM tracking 
            WHERE date(timestamp) BETWEEN ? AND ? 
            AND employee_name IS NOT NULL AND employee_name != ''
        '''
        params = [start_date, end_date]
        
        if employee_name_filter and employee_name_filter != "Todos":
            query += " AND employee_name = ?"
            params.append(employee_name_filter)
            
        query += " ORDER BY employee_name ASC, timestamp ASC"
        
        # Leemos con con fila de diccionarios para mayor claridad
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        # Agrupamos por empleado y día
        # key: (employee_name, date_str) -> value: list of records [(timestamp_datetime, inside_zone), ...]
        daily_records = {}
        for row in rows:
            emp_name = row['employee_name']
            r_date = row['r_date']
            ts_str = row['timestamp']
            inside = row['inside_zone']
            
            try:
                # ISO Format from datetime.now().isoformat()
                ts_dt = datetime.fromisoformat(ts_str)
            except ValueError:
                continue
                
            key = (emp_name, r_date)
            if key not in daily_records:
                daily_records[key] = []
            daily_records[key].append((ts_dt, inside))
            
        report_data = []
        
        # Procesar tiempos por día y empleado
        for (emp_name, d_date), records in daily_records.items():
            active_time_sec = 0.0
            inactive_time_sec = 0.0
            
            # Asumimos que están ordenados por timestamp
            for i in range(len(records) - 1):
                current_dt, current_inside = records[i]
                next_dt, _ = records[i+1]
                
                delta = (next_dt - current_dt).total_seconds()
                
                # Ignorar saltos locos (ej. si la cámara se apaga 5 horas, no lo contamos como tiempo seguido)
                # Un umbral lógico por "tracking continuo" sería p.ej. 5 minutos
                if delta > 300: 
                    continue
                    
                if current_inside == 1:
                    active_time_sec += delta
                else:
                    inactive_time_sec += delta
                    
            total_sec = active_time_sec + inactive_time_sec
            # Solo mostrar si hay tiempo registrado
            if total_sec <= 0:
                continue
            efficiency_pct = (active_time_sec / total_sec) * 100

            # Formatear salidas
            def format_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                return f"{hours}h {minutes}m"
                
            total_str = format_time(total_sec)
            active_str = format_time(active_time_sec)
            eff_str = f"{efficiency_pct:.1f}%"
            report_data.append((emp_name, d_date, total_str, active_str, eff_str))
                
        # Ordenar por fecha desc, nombre asc
        report_data.sort(key=lambda x: (x[1], x[0]), reverse=True)
        return report_data

    def get_employee_snapshots(self, employee_name, date_str):
        """
        Devuelve las rutas de snapshots para un empleado en una fecha específica.
        """
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT snapshot_path FROM snapshots
            WHERE employee_name = ? AND date(timestamp) = ?
            ORDER BY timestamp ASC
        """, (employee_name, date_str))
        rows = c.fetchall()
        conn.close()
        return [row[0] for row in rows if row[0]]

    def anonymize_employee(self, employee_name):
        """
        Reemplaza el nombre del empleado por un seudónimo anónimo en todas las tablas
        para preservar las métricas pero eliminar los datos personales (Derecho al olvido).
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        # Generar un hash corto o ID anónimo basado en el nombre y el tiempo
        import hashlib
        import time
        raw = f"{employee_name}_{time.time()}".encode('utf-8')
        anon_id = f"empleado_eliminado_{hashlib.sha256(raw).hexdigest()[:12]}"
        
        # _EMPLOYEE_NAME_TABLES es una constante de módulo hardcodeada — nunca proviene
        # de input del usuario, por lo que el f-string es seguro (OWASP A03).
        for table in _EMPLOYEE_NAME_TABLES:
            try:
                c.execute(f"UPDATE {table} SET employee_name = ? WHERE employee_name = ?", (anon_id, employee_name))  # nosec B608  # WAIVER-#6
            except sqlite3.OperationalError:
                pass # Ignorar si la tabla o columna no existe en versiones antiguas
                
        conn.commit()
        conn.close()
        
        return anon_id

    def delete_employee_profile(self, employee_name):
        """Elimina el registro del empleado de la tabla employees para permitir re-registro."""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM employees WHERE employee_name = ?", (employee_name,))
        conn.commit()
        conn.close()
