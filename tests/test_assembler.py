import unittest
import os
import sqlite3
import tempfile
from pathlib import Path
from core.database import ULMDatabase
from core.assembler import DynamicPromptAssembler

class TestDynamicPromptAssembler(unittest.TestCase):
    def setUp(self):
        # Create a temp database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.db = ULMDatabase(self.db_path)
        self.db.initialize_db()
        
        # Insert a developer profile metric to test retrieval
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO developer_profile (metric_id, category, name, description, confidence, frequency)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("m1", "strength", "sqlite-wal", "Understands SQLite write-ahead logging benefits.", 0.95, 3))
            conn.commit()
            
        self.workspace_root = tempfile.mkdtemp()
        self.vault_dir = Path(self.workspace_root) / ".vespera_memory"
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a mock vault file
        (self.vault_dir / "developer_profile.md").write_text("Focus: SQLite schema optimization.", encoding="utf-8")
        
        self.assembler = DynamicPromptAssembler(self.db_path, workspace_root=self.workspace_root)

    def tearDown(self):
        os.close(self.db_fd)
        try:
            os.remove(self.db_path)
        except OSError:
            pass
        # Clean up files in workspace
        for f in self.vault_dir.glob("*"):
            f.unlink()
        self.vault_dir.rmdir()
        os.rmdir(self.workspace_root)

    def test_assemble_prompt(self):
        prompt = self.assembler.assemble_prompt()
        self.assertIn("VESPERA CALIGO MASTER SYSTEM PROTOCOL", prompt)
        self.assertIn("sqlite-wal", prompt)
        self.assertIn("Focus: SQLite schema optimization.", prompt)
        self.assertIn("active system time is", prompt.lower())

if __name__ == "__main__":
    unittest.main()
