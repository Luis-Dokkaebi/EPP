import sys
import os
import unittest
from datetime import datetime, timedelta
import sqlite3

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from src.storage.database_manager import DatabaseManager

class TestReports(unittest.TestCase):
    def setUp(self):
        # Create a test database
        self.test_db_path = "data/db/test_tracking.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
            
        self.db = DatabaseManager(db_path=self.test_db_path)
        
        # Populate test data
        conn = sqlite3.connect(self.test_db_path)
        c = conn.cursor()
        
        # Insert test attendance
        c.execute("INSERT INTO daily_attendance (employee_name, date, arrival_time, departure_time) VALUES (?, ?, ?, ?)",
                  ("Juan Perez", "2023-10-01", "08:00:00", "17:00:00"))
        c.execute("INSERT INTO daily_attendance (employee_name, date, arrival_time, departure_time) VALUES (?, ?, ?, ?)",
                  ("Maria Gomez", "2023-10-01", "09:00:00", "13:30:00"))
                  
        # Insert test tracking for efficiency
        # Juan Perez active for 1 hour
        base_time = datetime(2023, 10, 1, 10, 0, 0)
        
        for i in range(12): # 12 pings, 5 mins apart -> 1 hour total
            ts = (base_time + timedelta(minutes=5*i)).isoformat()
            # Active in zone 1
            c.execute("INSERT INTO tracking (track_id, timestamp, x, y, zone, inside_zone, employee_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (1, ts, 100, 100, "ZonaA", 1, "Juan Perez"))
                      
        # Maria Gomez inactive for 30 mins
        base_time_m = datetime(2023, 10, 1, 11, 0, 0)
        for i in range(6): # 6 pings, 5 mins apart -> 30 mins total
            ts = (base_time_m + timedelta(minutes=5*i)).isoformat()
            c.execute("INSERT INTO tracking (track_id, timestamp, x, y, zone, inside_zone, employee_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (2, ts, 500, 500, "None", 0, "Maria Gomez"))

        conn.commit()
        conn.close()

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except:
                pass

    def test_get_unique_employees(self):
        emps = self.db.get_unique_employees()
        self.assertIn("Juan Perez", emps)
        self.assertIn("Maria Gomez", emps)
        self.assertEqual(len(emps), 2)

    def test_get_attendance_report(self):
        report = self.db.get_attendance_report("2023-10-01", "2023-10-01")
        self.assertEqual(len(report), 2)
        
        # Find Juan's record: unpacking (empleado, fecha, llegada, salida, horas_totales)
        juan_rec = next(r for r in report if r[0] == "Juan Perez")
        self.assertEqual(juan_rec[4], "9.00") # 8:00 to 17:00 is 9 hours
        
        maria_rec = next(r for r in report if r[0] == "Maria Gomez")
        self.assertEqual(maria_rec[4], "4.50") # 9:00 to 13:30 is 4.5 hours
        
        # Test filter
        filtered = self.db.get_attendance_report("2023-10-01", "2023-10-01", "Juan Perez")
        self.assertEqual(len(filtered), 1)

    def test_get_efficiency_report(self):
        report = self.db.get_efficiency_report("2023-10-01", "2023-10-01")
        
        # Juan has 12 pings (11 deltas of 5 mins) = 55 minutes active
        juan_rec = next(r for r in report if r[0] == "Juan Perez")
        self.assertEqual(juan_rec[4], "100.0%")
        
        # Maria has 6 pings (5 deltas of 5 mins) = 25 minutes inactive
        maria_rec = next(r for r in report if r[0] == "Maria Gomez")
        self.assertEqual(maria_rec[4], "0.0%")

if __name__ == '__main__':
    unittest.main()
