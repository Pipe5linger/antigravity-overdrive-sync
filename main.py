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

def sync_yaml_to_sqlite(db, yaml_state):
    """Parses updated YAML state and populates the SQLite database cleanly."""
    chats = yaml_state.get("chats", {})
    synced_sessions = 0
    synced_messages = 0

    for chat_id, chat_data in chats.items():
        last_mutated = chat_data.get("last_mutated", "")
        # Upsert the session
        db.upsert_session(chat_id, "antigravity", topics="Programming/Troubleshooting")
        synced_sessions += 1

        logs = chat_data.get("log", [])
        for log_entry in logs:
            role = log_entry.get("role", "")
            content = log_entry.get("content", "")
            created_at = log_entry.get("created_at") or last_mutated
            
            db.insert_message(chat_id, role, content, created_at)
            synced_messages += 1

    # Populate some default facts and preferences if the tables are empty
    try:
        with sqlite3.connect(db.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM preferences")
            if c.fetchone()[0] == 0:
                db.set_preference("persona", "Vespera Caligo")
                db.set_preference("origin", "Bordeaux, France")
                db.set_preference("beverage", "Vintage Red Wine")
                db.set_preference("humor", "Sarcastic, Sardonically Witty")
            
            c.execute("SELECT COUNT(*) FROM facts")
            if c.fetchone()[0] == 0:
                db.upsert_fact("User prefer local Ollama models (Qwen, DeepSeek)", "technical", 0.95)
                db.upsert_fact("Vespera Caligo acts as a real human physical mentor in France", "persona", 1.0)
    except sqlite3.Error:
        pass

    print(f"[+] ULM SQLite DB Sync Complete: {synced_sessions} sessions, {synced_messages} messages mapped.")

def main():
    register_plugins()
    
    parser = argparse.ArgumentParser(description="Universal Local Memory (ULM) Agent Pipeline")
    parser.add_argument("command", nargs="?", choices=["sync", "get-context"], default="sync",
                        help="Command to run: 'sync' (default) to run the full pipeline, or 'get-context' to query SQLite memory.")
    parser.add_argument("--parser", choices=list(PARSERS.keys()), default="antigravity",
                        help="Select the log extraction parser plugin")
    parser.add_argument("--injector", choices=list(INJECTORS.keys()), default="gemini_md",
                        help="Select the memory reinjection injector plugin")
    parser.add_argument("--dry-run", action="store_true",
                        help="Verify payload generation without mutating target prompt files")
    parser.add_argument("--platform", choices=["continue", "ollama", "gemini"], default="gemini",
                        help="Select target adapter platform for 'get-context'")
    parser.add_argument("--limit", type=int, default=5,
                        help="Limit recent messages/records returned for 'get-context'")
    
    args = parser.parse_args()
    
    # Define paths
    engine = ULMEngine()
    db_path = engine.target_yaml.replace(".yaml", ".db")
    db = ULMDatabase(db_path)
    db.initialize_db()

    # Command Router
    if args.command == "get-context":
        # Execute Adapter query
        if args.platform == "continue":
            adapter = ContinueConfigAdapter(db)
        elif args.platform == "ollama":
            adapter = OllamaModelfileAdapter(db)
        else:
            adapter = GeminiMarkdownAdapter(db)
            
        print(adapter.format_context())
        sys.exit(0)

    # Otherwise, execute default sync pipeline
    print("\n" + "="*60)
    print(f"🚀 INITIALIZING UNIVERSAL LOCAL MEMORY (ULM) PIPELINE")
    print(f"[*] Active Parser: {args.parser.upper()}")
    print(f"[*] Active Injector: {args.injector.upper()}")
    print(f"[*] Mode: {'DRY RUN (MUTATIONS BLOCKED)' if args.dry_run else 'PRODUCTION COMMIT'}")
    print("="*60)
    
    # 1. Initialize core ETL engine and load database state
    current_state = engine.load_existing_state()
    
    # 2. Instantiate and run selected parser
    parser_class = PARSERS[args.parser]
    log_parser = parser_class()
    
    print(f"[*] Running parser Stage 1 (Extract & Transform)...")
    new_logs = log_parser.fetch_new_logs()
    
    # 3. Merge logs into master database state
    updated_state, mutations = engine.merge_and_reconfigure(current_state, new_logs)
    
    if mutations > 0:
        if args.dry_run:
            print(f"[+] Dry run: ETL stage successfully staged {mutations} session modifications.")
        else:
            success = engine.commit_atomic_write(updated_state)
            if success:
                print(f"[+] ETL Stage Complete: Monolithic YAML database updated with {mutations} sessions.")
                # Sync new state directly into SQLite
                sync_yaml_to_sqlite(db, updated_state)
            else:
                print("[-] Critical Error: Atomic write commit failed.")
                sys.exit(1)
    else:
        print("[*] ETL Stage Complete: No new session modifications detected.")
        # Ensure SQLite is populated even if no new mutations are added to YAML
        sync_yaml_to_sqlite(db, current_state)
        
    # 4. Instantiate and run selected injector
    injector_class = INJECTORS[args.injector]
    memory_injector = injector_class()
    
    print(f"[*] Running injector Stage 2 (Load & Reinject)...")
    injection_success = memory_injector.inject(updated_state, dry_run=args.dry_run)
    
    if injection_success:
        print("="*60)
        print("[+] ULM Pipeline Execution completed successfully!")
        print("="*60 + "\n")
    else:
        print("[-] Pipeline halted during Reinjection Stage.")
        sys.exit(1)

if __name__ == "__main__":
    main()
