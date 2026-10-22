import unittest
import pandas as pd
import sqlite3
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.analysis.efficiency_calculator import EfficiencyCalculator

class TestEfficiency(unittest.TestCase):
    def setUp(self):
        self.db_path = "tests/data/db/test_eff.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE tracking (id INTEGER PRIMARY KEY, track_id INTEGER, timestamp TEXT, x REAL, y REAL, zone TEXT, inside_zone INTEGER)")
        c.execute("CREATE TABLE snapshots (id INTEGER PRIMARY KEY, track_id INTEGER, timestamp TEXT, zone TEXT, snapshot_path TEXT, employee_name TEXT)")
        
        # Insert data
        # Track 1: Visits ZoneA for 10 seconds. Snapshot has name "Juan".
        ts_start = "2023-01-01 10:00:00"
        ts_mid = "2023-01-01 10:00:05"
        ts_end = "2023-01-01 10:00:10"
        
        # Tracking: 0 (out), 1 (in), ..., 1 (in), 0 (out)
        data = [
            (1, "2023-01-01 09:59:59", 0, 0, "ZoneA", 0),
            (1, ts_start, 10, 10, "ZoneA", 1),
            (1, ts_mid, 11, 11, "ZoneA", 1),
            (1, ts_end, 12, 12, "ZoneA", 1),
            (1, "2023-01-01 10:00:11", 0, 0, "ZoneA", 0)
        ]
        c.executemany("INSERT INTO tracking (track_id, timestamp, x, y, zone, inside_zone) VALUES (?, ?, ?, ?, ?, ?)", data)
        
        # Snapshot at start time
        c.execute("INSERT INTO snapshots (track_id, timestamp, zone, snapshot_path, employee_name) VALUES (?, ?, ?, ?, ?)",
                  (1, ts_start, "ZoneA", "path.jpg", "Juan"))
        
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists("tests/data"):
            import shutil
            shutil.rmtree("tests/data")

    def test_calculation(self):
        calc = EfficiencyCalculator(db_path=self.db_path)
        df = calc.calculate_efficiency()
        
        self.assertIsNotNone(df)
        self.assertFalse(df.empty)
        row = df.iloc[0]
        self.assertEqual(row['track_id'], 1)
        self.assertEqual(row['employee_name'], "Juan")
        self.assertEqual(row['zone'], "ZoneA")
        # Duration approx 10s
        self.assertAlmostEqual(row['duration_sec'], 10.0, delta=1.0)

if __name__ == '__main__':
    unittest.main()
