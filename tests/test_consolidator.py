import unittest
from unittest.mock import patch, MagicMock
import os
import sqlite3
import json
import tempfile
from core.database import ULMDatabase
from core.consolidator import MemoryConsolidator

class TestMemoryConsolidator(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.db = ULMDatabase(self.db_path)
        self.db.initialize_db()
        self.consolidator = MemoryConsolidator(self.db)

        # Populate temporary facts
        with self.db.get_connection() as conn:
            c = conn.cursor()
            # F1 and F2 are redundant/contradictory
            c.execute("""
                INSERT INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("f1", "Pilot prefers using poetry for Python packaging", "technical", 0.9, "2026-06-17T00:00:00Z", "2026-06-17T00:00:00Z", "antigravity"))
            c.execute("""
                INSERT INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("f2", "Pilot wants pipenv instead of poetry", "technical", 0.8, "2026-06-17T01:00:00Z", "2026-06-17T01:00:00Z", "antigravity"))
            conn.commit()

    def tearDown(self):
        os.close(self.db_fd)
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    @patch("requests.post")
    def test_consolidate_local_ollama(self, mock_post):
        self.db.set_preference("llm_provider", "local_ollama")

        # Mock Ollama output to perform deletion and upsert
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": json.dumps({
                "deletions": ["f1", "f2"],
                "upserts": [
                    {
                        "fact": "Pilot switched from poetry to pipenv for python packaging",
                        "category": "technical",
                        "confidence": 0.95,
                        "project_tag": "antigravity"
                    }
                ]
            }),
            "done": True
        }
        mock_post.return_value = mock_response

        # Execute consolidation
        deleted, upserted = self.consolidator.consolidate()
        
        # Verify counts
        self.assertEqual(deleted, 2)
        self.assertEqual(upserted, 1)

        # Query database to check state
        facts = self.db.get_facts(project_tag="antigravity")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["fact"], "Pilot switched from poetry to pipenv for python packaging")
        self.assertEqual(facts[0]["project_tag"], "antigravity")

if __name__ == "__main__":
    unittest.main()
