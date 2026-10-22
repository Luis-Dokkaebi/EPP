import sys
import os
import unittest
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.analysis.efficiency_calculator import EfficiencyCalculator
from src.storage.database_manager import DatabaseManager

class TestReportGeneration(unittest.TestCase):
    def setUp(self):
        self.db_path = "data/db/test_tracking.db"
        # Ensure clean state
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        # Ensure dir exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.db_manager = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_calculate_efficiency(self):
        # 1. Insert Mock Data
        # Visit 1: Track 1, Zone A, 10 frames, moving a bit
        start_time = datetime(2023, 10, 27, 10, 0, 0)
        track_id = 1
        zone = "Zone_A"

        # Snapshot at entry
        snapshot_path = "data/snapshots/test_snap.jpg"
        self.db_manager.insert_snapshot(track_id, zone, snapshot_path)
        # Manually update timestamp to match start_time because insert_snapshot uses now()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE snapshots SET timestamp = ? WHERE track_id = ?", (start_time.isoformat(), track_id))
        conn.commit()
        conn.close()

        # Tracking data
        # We need sequential inserts to simulate visit
        for i in range(10):
            t = start_time + timedelta(seconds=i)
            # Add some jitter to x, y
            x = 100 + (i % 2) * 5 # 100, 105, 100, 105...
            y = 200 + (i % 3) * 5
            self.db_manager.insert_record(track_id, x, y, zone, inside_zone=1)

            # Update timestamp manually
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            # Get last id
            last_id = c.execute("SELECT MAX(id) FROM tracking").fetchone()[0]
            c.execute("UPDATE tracking SET timestamp = ? WHERE id = ?", (t.isoformat(), last_id))
            conn.commit()
            conn.close()

        # 2. Run Calculator
        calculator = EfficiencyCalculator(db_path=self.db_path)
        df = calculator.calculate_efficiency()

        # 3. Verify
        print("\nResulting DataFrame:")
        print(df)
        self.assertIsNotNone(df)
        self.assertFalse(df.empty)
        row = df.iloc[0]

        self.assertEqual(row['track_id'], track_id)
        self.assertEqual(row['zone'], zone)
        self.assertEqual(row['snapshot_path'], snapshot_path)
        self.assertGreater(row['duration_sec'], 8) # Should be around 9 seconds
        self.assertGreater(row['productivity_score'], 0) # Should have some activity due to jitter

if __name__ == '__main__':
    unittest.main()
