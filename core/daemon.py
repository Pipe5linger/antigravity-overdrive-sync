import os
import sys
import asyncio
import time
from pathlib import Path
from core.database import ULMDatabase
from core.engine import ULMEngine
from core.fact_extractor import FactExtractor
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
        self.queue = asyncio.Queue()
        self.extractor = FactExtractor()

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

    def _get_session_dialogue(self, session_id):
        """Quickly fetch formatted dialogue for a session to check for signals."""
        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
                msgs = c.fetchall()
                return "\n".join([f"{m[0]}: {m[1]}" for m in msgs])
        except Exception as e:
            print(f"[-] Daemon: Error fetching dialogue for {session_id[:8]}: {e}")
            return ""

    def _run_maintenance(self):
        """Synchronous maintenance tasks: consolidation and rule injection."""
        try:
            from core.consolidator import MemoryConsolidator
            consolidator = MemoryConsolidator(self.db)
            consolidator.consolidate()
        except Exception as e:
            print(f"[-] Daemon: Fact consolidation failed: {e}")
        
        try:
            injector = ClineRulesInjector()
            if injector.inject(self.db):
                print("[+] Daemon: Successfully refreshed Cline rule files.")
        except Exception as e:
            print(f"[-] Daemon: Rule injection failed: {e}")

    async def _worker(self):
        """Background worker that processes high-signal sessions one at a time."""
        print("[*] Daemon: Background LLM worker active.")
        from core.profile_evaluator import ProfileEvaluator
        evaluator = ProfileEvaluator()
        
        while True:
            s_id = await self.queue.get()
            try:
                # Run the heavy LLM evaluation in a separate thread to avoid blocking the event loop
                await asyncio.to_thread(evaluator.evaluate_session, self.db, s_id)
                # Mark as profiled after successful evaluation
                await asyncio.to_thread(self.db.mark_session_profiled, s_id)
            except Exception as e:
                print(f"[-] Daemon: Background evaluation failed for session {s_id[:8]}: {e}")
            finally:
                self.queue.task_done()

    async def run_sync_cycle(self):
        """Fetches logs, updates SQLite, and queues high-signal sessions for evaluation."""
        print("[*] Daemon: Initiating automatic synchronization cycle...")
        
        # Use to_thread for blocking I/O
        new_logs = await asyncio.to_thread(self.parser.fetch_new_logs, force_ingest=True)
        
        if new_logs:
            await asyncio.to_thread(self.db.import_raw_logs, new_logs)
            print(f"[+] Daemon: Ingested {len(new_logs)} session deltas to database.")
            
            unprofiled = await asyncio.to_thread(self.db.get_unprofiled_sessions)
            if unprofiled:
                for s_id in unprofiled:
                    # Offload DB fetch to thread to ensure the tick remains ultra-fast
                    dialogue = await asyncio.to_thread(self._get_session_dialogue, s_id)
                    if not self.extractor.has_signal(dialogue):
                        # Instant clear zero-signal sessions
                        await asyncio.to_thread(self.db.mark_session_profiled, s_id)
                    else:
                        # Queue high-signal sessions for the background worker
                        await self.queue.put(s_id)
                
                print(f"[*] Daemon: Queued {len(unprofiled)} sessions for evaluation.")

            # Run maintenance in thread
            await asyncio.to_thread(self._run_maintenance)
        else:
            print("[*] Daemon: No new updates processed.")

    async def start(self):
        """Starts the main background loop."""
        print(f"[+] ULM Daemon active. Watching directories: {self.watched_dirs}")
        print(f"[+] Watch polling interval set to {self.interval} seconds. Press Ctrl+C to terminate.")
        
        # Start the background worker
        worker_task = asyncio.create_task(self._worker())
        
        # Initial scan to establish baseline (offloaded to thread)
        await asyncio.to_thread(self.scan_transcripts)
        
        # Proactively run a sync cycle on startup
        await self.run_sync_cycle()
        
        try:
            while True:
                await asyncio.sleep(self.interval)
                # Offload directory scanning to thread to keep tick < 5ms
                updates = await asyncio.to_thread(self.scan_transcripts)
                if updates:
                    await self.run_sync_cycle()
        except asyncio.CancelledError:
            worker_task.cancel()
            print("\n[-] Daemon: Process terminated.")

if __name__ == "__main__":
    daemon = ULMDaemon()
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        sys.exit(0)
