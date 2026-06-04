import os
import sys
import unittest
import sqlite3
import tempfile
import shutil
import time

# Dynamic path resolution to import ULM modules
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_PATH = os.path.dirname(TESTS_DIR)
sys.path.append(REPO_PATH)

from core.database import ULMDatabase

class TestULMDatabase(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test database files
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_ulm.db")
        self.db = ULMDatabase(self.db_path)
        self.db.initialize_db()

    def tearDown(self):
        # Allow SQLite connection pool to fully release locks
        time.sleep(0.1)
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass # Gracefully handle OS permission anomalies during cleanup

    def test_database_initialization(self):
        """Verifies that all SQLite tables and schema versioning are set up correctly."""
        self.assertTrue(os.path.exists(self.db_path))
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            # Verify tables exist
            c.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in c.fetchall()]
            self.assertIn("schema_version", tables)
            self.assertIn("sessions", tables)
            self.assertIn("messages", tables)
            self.assertIn("facts", tables)
            self.assertIn("preferences", tables)

            # Verify Schema Version is initialized to 2
            c.execute("SELECT version FROM schema_version;")
            version = c.fetchone()[0]
            self.assertEqual(version, 2)

    def test_session_upsert(self):
        """Verifies that sessions are successfully inserted and updated."""
        session_id = "session_abc"
        self.db.upsert_session(session_id, "test_source", "Testing/Verification")
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT source, topics FROM sessions WHERE session_id = ?;", (session_id,))
            row = c.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "test_source")
            self.assertEqual(row[1], "Testing/Verification")

    def test_message_deduplication(self):
        """Verifies that duplicate messages are ignored at the database level using stable hashes."""
        session_id = "session_abc"
        self.db.upsert_session(session_id, "test_source", "Testing/Verification")
        
        role = "user"
        content = "Hello, Vespera!"
        timestamp = "2026-06-01T12:00:00Z"
        
        # Insert once
        self.db.insert_message(session_id, role, content, timestamp)
        
        # Attempt duplicate insertion
        self.db.insert_message(session_id, role, content, timestamp)
        
        # Verify only one row exists in the database
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?;", (session_id,))
            count = c.fetchone()[0]
            self.assertEqual(count, 1)

    def test_fact_deduplication(self):
        """Verifies that facts are deterministically hashed and deduplicated."""
        fact_text = "Vespera Caligo drinks vintage red wine."
        
        # Insert twice
        self.db.upsert_fact(fact_text, "personality", 1.0)
        self.db.upsert_fact(fact_text, "personality", 1.0)
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM facts;")
            count = c.fetchone()[0]
            self.assertEqual(count, 1)

    def test_context_retrieval(self):
        """Verifies that recent context is fetched in correct chronological order."""
        session_id = "session_abc"
        self.db.upsert_session(session_id, "test_source", "Testing/Verification")
        
        # Insert messages with incremental timestamps
        self.db.insert_message(session_id, "user", "Message 1", "2026-06-01T12:00:00Z")
        self.db.insert_message(session_id, "model", "Message 2", "2026-06-01T12:01:00Z")
        
        context = self.db.get_recent_context(limit=10)
        self.assertEqual(len(context), 2)
        
        # Verify chronological order (most recent first)
        self.assertEqual(context[0][1], "model")  # role
        self.assertEqual(context[0][2], "Message 2")  # content
        self.assertEqual(context[1][2], "Message 1")

if __name__ == "__main__":
    unittest.main()
