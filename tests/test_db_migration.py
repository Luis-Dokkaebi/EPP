import unittest
import os
import sqlite3
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.storage.database_manager import DatabaseManager

class TestDBMigration(unittest.TestCase):
    def setUp(self):
        self.db_path = "tests/data/db/test.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists("tests/data"):
            import shutil
            shutil.rmtree("tests/data")

    def test_schema_creation(self):
        # Initialize manager, should create table
        manager = DatabaseManager(db_path=self.db_path)
        
        # Verify column exists
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("PRAGMA table_info(snapshots)")
        columns = [info[1] for info in c.fetchall()]
        conn.close()
        
        self.assertIn("employee_name", columns)

    def test_insert_snapshot_with_name(self):
        manager = DatabaseManager(db_path=self.db_path)
        manager.insert_snapshot(track_id=1, zone="ZoneA", snapshot_path="path/to/snap.jpg", employee_name="Juan")
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT employee_name FROM snapshots WHERE track_id=1")
        row = c.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Juan")

if __name__ == '__main__':
    unittest.main()
