import sys
import os
import argparse
import sqlite3

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Import core elements
from core.engine import ULMEngine
from core.database import ULMDatabase
from core.adapters import ContinueConfigAdapter, OllamaModelfileAdapter, GeminiMarkdownAdapter

# Registry of plugins
PARSERS = {}
INJECTORS = {}

# Lazy load plugins to prevent circular imports and allow modular dependency structures
def register_plugins():
    try:
        from parsers.antigravity import AntigravityParser
        PARSERS["antigravity"] = AntigravityParser
    except Exception as e:
        print(f"[-] Failed to register AntigravityParser: {e}")

    try:
        from injectors.gemini_md import GeminiMdInjector
        INJECTORS["gemini_md"] = GeminiMdInjector
    except Exception as e:
        print(f"[-] Failed to register GeminiMdInjector: {e}")

    try:
        from injectors.ollama_modelfile import OllamaInjector
        INJECTORS["ollama"] = OllamaInjector
    except Exception as e:
        print(f"[-] Failed to register OllamaInjector: {e}")

def backup_sqlite_to_yaml(db, engine):
    """Reads all session and message history from SQLite and exports it to the monolithic YAML file."""
    import yaml
    import datetime
    chats = {}
    total_chats = 0
    try:
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT session_id, updated_at, topics, summary FROM sessions")
            sessions = c.fetchall()
            total_chats = len(sessions)
            
            for s in sessions:
                session_id = s["session_id"]
                updated_at = s["updated_at"]
                topics = s["topics"]
                summary = s["summary"]
                
                c.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
                msgs = c.fetchall()
                
                log_entries = []
                for m in msgs:
                    log_entries.append({
                        "role": m["role"],
                        "content": m["content"],
                        "created_at": m["created_at"]
                    })
                
                chats[session_id] = {
                    "last_mutated": updated_at,
                    "log": log_entries
                }
                if summary:
                    chats[session_id]["summary"] = summary
                    
        yaml_state = {
            "metadata": {
                "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "total_chats": total_chats
            },
            "chats": chats
        }
        
        success = engine.commit_atomic_write(yaml_state)
        if success:
            print(f"[+] Backup Complete: SQLite database exported successfully to {engine.target_yaml}")
        else:
            print("[-] Backup failed: could not write to YAML file.")
    except Exception as e:
        print(f"[-] Error during backup: {e}")

def main():
    register_plugins()
    
    parser = argparse.ArgumentParser(description="Universal Local Memory (ULM) Agent Pipeline")
    parser.add_argument("command", nargs="?", choices=["sync", "get-context", "tui"], default="sync",
                        help="Command to run: 'sync' (default) to run the full pipeline, 'get-context' to query SQLite memory, or 'tui' for interactive dashboard.")
    parser.add_argument("--parser", choices=list(PARSERS.keys()), default="antigravity",
                        help="Select the log extraction parser plugin")
    parser.add_argument("--injector", choices=list(INJECTORS.keys()), default="gemini_md",
                        help="Select the memory reinjection injector plugin")
    parser.add_argument("--dry-run", action="store_true",
                        help="Verify payload generation without mutating target prompt files")
    parser.add_argument("--backup", action="store_true",
                        help="Snapshot and back up SQLite state back to the monolithic YAML file.")
    parser.add_argument("--platform", choices=["continue", "ollama", "gemini"], default="gemini",
                        help="Select target adapter platform for 'get-context'")
    parser.add_argument("--limit", type=int, default=5,
                        help="Limit recent messages/records returned for 'get-context'")
    
    args = parser.parse_args()
    
    # Define paths
    engine = ULMEngine()
    from pathlib import Path
    db_path = str(Path(engine.target_yaml).with_suffix(".db"))
    db = ULMDatabase(db_path)
    db.initialize_db()

    # Command Router
    if args.command == "get-context":
        if args.platform == "continue":
            adapter = ContinueConfigAdapter(db)
        elif args.platform == "ollama":
            adapter = OllamaModelfileAdapter(db)
        else:
            adapter = GeminiMarkdownAdapter(db)
            
        print(adapter.format_context())
        sys.exit(0)
    elif args.command == "tui":
        from tui.dashboard import ULMTUIDashboard
        dashboard = ULMTUIDashboard()
        dashboard.start()
        sys.exit(0)

    # Otherwise, execute default sync pipeline
    print("\n" + "="*60)
    print(f"🚀 INITIALIZING UNIVERSAL LOCAL MEMORY (ULM) PIPELINE")
    print(f"[*] Active Parser: {args.parser.upper()}")
    print(f"[*] Active Injector: {args.injector.upper()}")
    print(f"[*] Mode: {'DRY RUN (MUTATIONS BLOCKED)' if args.dry_run else 'PRODUCTION COMMIT'}")
    print(f"[*] YAML Backup: {'ENABLED' if args.backup else 'DISABLED'}")
    print("="*60)
    
    # 1. Instantiate and run selected parser
    parser_class = PARSERS[args.parser]
    log_parser = parser_class()
    
    print(f"[*] Running parser Stage 1 (Extract & Transform)...")
    new_logs = log_parser.fetch_new_logs()
    
    # 2. Merge/Ingest logs directly into SQLite database
    if new_logs:
        if args.dry_run:
            print(f"[+] Dry run: ETL stage successfully staged {len(new_logs)} session modifications.")
        else:
            db.import_raw_logs(new_logs)
            
            # Run profile evaluation only on sessions not yet profiled
            try:
                from core.profile_evaluator import ProfileEvaluator
                evaluator = ProfileEvaluator()
                unprofiled = db.get_unprofiled_sessions()
                if unprofiled:
                    print(f"[*] Evaluating {len(unprofiled)} unprofiled session(s)...")
                    for session_id in unprofiled:
                        success = evaluator.evaluate_session(db, session_id)
                        if success:
                            db.mark_session_profiled(session_id)
                        elif evaluator.quota_exhausted:
                            print(f"[!] API quota exhausted. Stopping profile evaluation — will resume next sync.")
                            break
                else:
                    print("[*] Profile evaluation: all sessions already profiled, skipping.")
            except Exception as pe_err:
                print(f"[-] Profile evaluation warning: {pe_err}")
    else:
        print("[*] ETL Stage Complete: No new session modifications detected.")
        
    # 3. Handle backup command flag
    if args.backup and not args.dry_run:
        backup_sqlite_to_yaml(db, engine)
        
    # 4. Instantiate and run selected injector
    injector_class = INJECTORS[args.injector]
    memory_injector = injector_class()
    
    print(f"[*] Running injector Stage 2 (Load & Reinject)...")
    injection_success = memory_injector.inject(db, dry_run=args.dry_run)
    
    if injection_success:
        print("="*60)
        print("[+] ULM Pipeline Execution completed successfully!")
        print("="*60 + "\n")
    else:
        print("[-] Pipeline halted during Reinjection Stage.")
        sys.exit(1)

if __name__ == "__main__":
    main()

