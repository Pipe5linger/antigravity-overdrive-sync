import sys
import os
import argparse
import sqlite3
from pathlib import Path

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Import core elements
from core.database import ULMDatabase
from core.engine import ULMEngine
from core.adapters import ContinueConfigAdapter, OllamaModelfileAdapter
from core.blended_adapter import BlendedMarkdownAdapter

# Registry of plugins
PARSERS = {}
INJECTORS = {}

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
    try:
        from injectors.cline_rules import ClineRulesInjector
        INJECTORS["cline_rules"] = ClineRulesInjector
    except Exception as e:
        print(f"[-] Failed to register ClineRulesInjector: {e}")

def backup_sqlite_to_yaml(db, engine):
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
                c.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
                msgs = c.fetchall()
                log_entries = [{"role": m["role"], "content": m["content"], "created_at": m["created_at"]} for m in msgs]
                chats[session_id] = {"last_mutated": s["updated_at"], "log": log_entries}
                if s["summary"]: chats[session_id]["summary"] = s["summary"]
        yaml_state = {"metadata": {"last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "total_chats": total_chats}, "chats": chats}
        if engine.commit_atomic_write(yaml_state):
            print(f"[+] Backup Complete: {engine.target_yaml}")
    except Exception as e:
        print(f"[-] Error during backup: {e}")

def main():
    register_plugins()
    parser = argparse.ArgumentParser(description="Universal Local Memory (ULM) Agent Pipeline")
    parser.add_argument("command", nargs="?", choices=["sync", "get-context", "tui", "daemon"], default="sync")
    parser.add_argument("--parser", choices=list(PARSERS.keys()), default="antigravity")
    parser.add_argument("--injector", choices=list(INJECTORS.keys()), default="gemini_md")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--manual", action="store_true")
    parser.add_argument("--llm-model", type=str, help="Specify the exact LLM model string for the injector/parser")
    parser.add_argument("--vector-model", type=str, help="Specify the embedding model string for vectorization")
    args = parser.parse_args()
    
    engine = ULMEngine(llm_model=args.llm_model, vector_model=args.vector_model)
    db_path = str(Path(engine.target_yaml).with_suffix(".db"))
    db = ULMDatabase(db_path)
    db.initialize_db()

    if args.command == "tui":
        from tui.dashboard import ULMTUIDashboard
        app = ULMTUIDashboard()
        app.start()

    elif args.command == "daemon":
        from core.daemon import ULMDaemon
        daemon = ULMDaemon()
        daemon.start()

    elif args.command == "sync":
        print(f"\n[*] ULM Pipeline Initialized | Parser: {args.parser.upper()} | Injector: {args.injector.upper()}")
        
        parser_class = PARSERS[args.parser]
        log_parser = parser_class(llm_model=args.llm_model, vector_model=args.vector_model)
        new_logs = log_parser.fetch_new_logs()
        
        if new_logs:
            if not args.dry_run:
                db.import_raw_logs(new_logs)
                print(f"[+] ETL Complete: Ingested {len(new_logs)} session modifications.")
                
                # Evaluate new sessions
                try:
                    from core.profile_evaluator import ProfileEvaluator
                    evaluator = ProfileEvaluator()
                    unprofiled = db.get_unprofiled_sessions()
                    if unprofiled:
                        print(f"[*] Running developer profile evaluation on {len(unprofiled)} sessions...")
                        for s_id in unprofiled:
                            if evaluator.evaluate_session(db, s_id):
                                db.mark_session_profiled(s_id)
                except Exception as e:
                    print(f"[-] Profile evaluation failed: {e}")
        else:
            print("[*] No new logs detected.")

        if args.backup and not args.dry_run:
            backup_sqlite_to_yaml(db, engine)
            
        if args.manual:
            print("[*] Running Injector Stage 2 (Local Structural Reinjection)...")
            injector_class = INJECTORS[args.injector]
            memory_injector = injector_class(llm_model=args.llm_model, vector_model=args.vector_model)
            if memory_injector.inject(db, dry_run=args.dry_run):
                print("[+] ULM Pipeline Execution completed successfully!")
            else:
                print("[-] Pipeline halted during Reinjection Stage.")
                sys.exit(1)
        else:
            print("[!] Background Sync Complete. Run with '--manual' to update project files.")

if __name__ == "__main__":
    main()