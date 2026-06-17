import unittest
import os
import tempfile
import time
from pathlib import Path
from core.daemon import ULMDaemon

class TestULMDaemon(unittest.TestCase):
    def setUp(self):
        # Create a temp directory to simulate a watched workspace
        self.temp_dir = tempfile.mkdtemp()
        self.daemon = ULMDaemon(interval=1)
        self.daemon.watched_dirs = [self.temp_dir]

    def tearDown(self):
        # Clean up files in temp directory
        for f in Path(self.temp_dir).glob("**/*"):
            if f.is_file():
                f.unlink()
        os.rmdir(self.temp_dir)

    def test_scan_and_detect_updates(self):
        # 1. Establish baseline scan
        test_file = Path(self.temp_dir) / "transcript.jsonl"
        test_file.write_text("initial logs", encoding="utf-8")
        
        # Initial scan registers the baseline mtime
        self.daemon.scan_transcripts()
        self.assertIn(str(test_file), self.daemon.mtimes)
        
        # 2. Modify file and check if daemon detects update
        time.sleep(1.1)  # Ensure file system timestamp changes
        test_file.write_text("updated logs", encoding="utf-8")
        
        updates = self.daemon.scan_transcripts()
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0], str(test_file))

if __name__ == "__main__":
    unittest.main()
