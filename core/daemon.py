import os
import sys
import time
from pathlib import Path
from core.database import ULMDatabase
from core.engine import ULMEngine
from parsers.antigravity import AntigravityParser
from injectors.cline_rules import ClineRulesInjector

class ULMDaemon:
    """Background file-watcher daemon that detects session updates, runs ingestion, and refreshes rule files."""
    
    def __init__(self, interval=5):
        self.interval = interval
        self.engine = ULMEngine()
        db_path = str(Path(self.engine.target_yaml).with_suffix(".db"))
        self.db = ULMDatabase(db_path)
        self.db.initialize_db()
        
        # Pull source directories to watch from the active parser
        self.parser = AntigravityParser()
        self.watched_dirs = self.parser.source_dirs
        
        # Keep track of file modification times
        self.mtimes = {}

    def scan_transcripts(self):
        """Scans watched directories for updated transcripts and returns a list of modified paths."""
        modified_paths = []
        for target_dir in self.watched_dirs:
            if not os.path.exists(target_dir):
                continue
            
            for item in os.listdir(target_dir):
                full_path = os.path.join(target_dir, item)
                
                # Deduce path to standard logs
                if os.path.isdir(full_path):
                    transcript_path = os.path.join(full_path, ".system_generated", "logs", "transcript.jsonl")
                else:
                    transcript_path = full_path
                
                if os.path.exists(transcript_path):
                    mtime = os.path.getmtime(transcript_path)
                    prev_mtime = self.mtimes.get(transcript_path)
                    
                    if prev_mtime is None:
                        # Initial scan: register current timestamp without triggering sync
                        self.mtimes[transcript_path] = mtime
                    elif mtime > prev_mtime:
                        print(f"[+] Daemon: Detected update in transcript: {transcript_path}")
                        self.mtimes[transcript_path] = mtime
                        modified_paths.append(transcript_path)
        return modified_paths

    def run_sync_cycle(self):
        """Fetches logs, updates SQLite, and triggers rule injections."""
        print("[*] Daemon: Initiating automatic synchronization cycle...")
        new_logs = self.parser.fetch_new_logs(force_ingest=True)
        if new_logs:
            self.db.import_raw_logs(new_logs)
            print(f"[+] Daemon: Ingested {len(new_logs)} session deltas to database.")
            
            # Evaluate new sessions
            try:
                from core.profile_evaluator import ProfileEvaluator
                evaluator = ProfileEvaluator()
                unprofiled = self.db.get_unprofiled_sessions()
                if unprofiled:
                    print(f"[*] Daemon: Found {len(unprofiled)} unprofiled sessions. Running evaluator...")
                    for s_id in unprofiled:
                        if evaluator.evaluate_session(self.db, s_id):
                            self.db.mark_session_profiled(s_id)
            except Exception as e:
                print(f"[-] Daemon: Profile evaluation failed: {e}")
            
            # Refresh rules
            injector = ClineRulesInjector()
            if injector.inject(self.db):
                print("[+] Daemon: Successfully refreshed Cline rule files.")
        else:
            print("[*] Daemon: No new updates processed.")

    def start(self):
        """Starts the main background loop."""
        print(f"[+] ULM Daemon active. Watching directories: {self.watched_dirs}")
        print(f"[+] Watch polling interval set to {self.interval} seconds. Press Ctrl+C to terminate.")
        
        # Initial scan to establish baseline
        self.scan_transcripts()
        
        try:
            while True:
                time.sleep(self.interval)
                updates = self.scan_transcripts()
                if updates:
                    self.run_sync_cycle()
        except KeyboardInterrupt:
            print("\n[-] Daemon: Process terminated by Operator.")
            sys.exit(0)

if __name__ == "__main__":
    daemon = ULMDaemon()
    daemon.start()
