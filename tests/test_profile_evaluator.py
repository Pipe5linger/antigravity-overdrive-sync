import unittest
from unittest.mock import patch, MagicMock
import os
import sqlite3
import json

from core.database import ULMDatabase
from core.profile_evaluator import ProfileEvaluator

class TestProfileEvaluator(unittest.TestCase):
    def setUp(self):
        # Use a temporary database file for test isolation
        self.db_path = "test_temp.db"
        self.db = ULMDatabase(self.db_path)
        self.db.initialize_db()
        self.evaluator = ProfileEvaluator(api_key="TEST_API_KEY")

        # Set up a mock session and messages, clearing any leftover test data
        self.session_id = "test_session_123"
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM developer_profile;")
            c.execute("DELETE FROM messages;")
            c.execute("DELETE FROM sessions;")
            
            c.execute("""
                INSERT OR REPLACE INTO sessions (session_id, source, created_at, updated_at, topics)
                VALUES (?, ?, ?, ?, ?)
            """, (self.session_id, "test", "2026-06-17T00:00:00Z", "2026-06-17T00:00:00Z", "Testing"))
            
            c.execute("""
                INSERT OR REPLACE INTO messages (message_id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, ("msg1", self.session_id, "Pilot", "I just set up sqlite WAL mode and git commits.", "2026-06-17T00:00:01Z"))
            
            c.execute("""
                INSERT OR REPLACE INTO messages (message_id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, ("msg2", self.session_id, "Vespera", "Excellent work, WAL keeps concurrency fast.", "2026-06-17T00:00:02Z"))
            conn.commit()

    def tearDown(self):
        # Clean up temporary database file
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except:
                pass

    @patch("requests.post")
    def test_evaluate_session_local_ollama(self, mock_post):
        # Configure database preferences for local ollama
        self.db.set_preference("llm_provider", "local_ollama")
        self.db.set_preference("llm_model", "qwen2.5-coder:14b")
        self.db.set_preference("ollama_endpoint", "http://localhost:11434")

        # Mock response from Ollama API with metrics schema inside response string
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": json.dumps({
                "metrics": [{
                    "category": "strength",
                    "name": "sqlite-wal-understanding",
                    "description": "Demonstrated understanding of SQLite WAL concurrency advantages.",
                    "confidence": 0.95
                }]
            }),
            "done": True
        }
        mock_post.return_value = mock_response

        # Execute evaluation using the database upsert spy
        with patch.object(self.db, "upsert_profile_metric") as mock_upsert:
            success = self.evaluator.evaluate_session(self.db, self.session_id)
            self.assertTrue(success)
            mock_upsert.assert_called_once_with("strength", "sqlite-wal-understanding", "Demonstrated understanding of SQLite WAL concurrency advantages.", 0.95)

    @patch("urllib.request.urlopen")
    def test_evaluate_session_cloud_gemini(self, mock_urlopen):
        # Configure database preferences for cloud gemini
        self.db.set_preference("llm_provider", "cloud_gemini")
        self.db.set_preference("gemini_api_key", "MOCK_KEY_123")

        # Mock HTTP response from Google Generative Language API
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "metrics": [
                                        {
                                            "category": "milestone",
                                            "name": "git-setup",
                                            "description": "Completed repository tracking setup.",
                                            "confidence": 0.85
                                        }
                                    ]
                                })
                            }
                        ]
                    }
                }
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Execute evaluation using the database upsert spy
        with patch.object(self.db, "upsert_profile_metric") as mock_upsert:
            success = self.evaluator.evaluate_session(self.db, self.session_id)
            self.assertTrue(success)
            mock_upsert.assert_called_once_with("milestone", "git-setup", "Completed repository tracking setup.", 0.85)

if __name__ == "__main__":
    unittest.main()

