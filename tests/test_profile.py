import unittest
import os
import tempfile
import shutil
import time
from core.database import ULMDatabase

class TestProfileDatabase(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the test database file
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_profile.db")
        self.db = ULMDatabase(self.db_path)
        self.db.initialize_db()

    def tearDown(self):
        # Clean up the test database file after running
        time.sleep(0.1)
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_database_profile_operations(self):
        # 1. Verify metric insertion
        self.db.upsert_profile_metric(
            category="milestone", 
            name="vscode-navigation", 
            description="Mastered VS Code search hotkeys", 
            confidence=0.95
        )
        
        profile = self.db.get_developer_profile()
        self.assertEqual(len(profile), 1)
        self.assertEqual(profile[0]["category"], "milestone")
        self.assertEqual(profile[0]["name"], "vscode-navigation")
        self.assertEqual(profile[0]["frequency"], 1)
        
        # 2. Verify frequency increment and last_seen updates
        first_seen = profile[0]["first_seen"]
        
        self.db.upsert_profile_metric(
            category="milestone", 
            name="vscode-navigation", 
            description="Mastered VS Code search hotkeys again", 
            confidence=0.98
        )
        
        updated_profile = self.db.get_developer_profile()
        self.assertEqual(len(updated_profile), 1)
        self.assertEqual(updated_profile[0]["frequency"], 2)
        self.assertEqual(updated_profile[0]["confidence"], 0.98)
        self.assertEqual(updated_profile[0]["first_seen"], first_seen)