import sys
import os
import json
import argparse
import sqlite3
import asyncio
from pathlib import Path

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
    except AttributeError:
        pass

# Load environment variables from .env file overriding standard ones
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
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
    try:
        from injectors.google_docs import GoogleDocsInjector
        INJECTORS["google_docs"] = GoogleDocsInjector
    except Exception as e:
        print(f"[-] Failed to register GoogleDocsInjector: {e}")
    try:
        from injectors.copilot import CopilotInjector
        INJECTORS["copilot"] = CopilotInjector
    except Exception as e:
        print(f"[-] Failed to register CopilotInjector: {e}")

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
    parser.add_argument("command", nargs="?", choices=["sync", "get-context", "tui", "webui", "daemon", "search", "recall"], default="sync")
    parser.add_argument("--query", "-q", type=str, help="Search query for memory database")
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

    if args.command == "search":
        query_text = args.query or " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        if not query_text:
            print("[-] Please specify a search term using --query 'search string'")
            return
        results = db.search_memory_db(query_text)
        print(json.dumps(results, indent=2))
        return

    if args.command == "recall":
        query_text = args.query or " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        if not query_text:
            print("[-] Please specify a recall query using --query 'semantic question'")
            return
        from core.consolidator import MemoryConsolidator
        consolidator = MemoryConsolidator(db)
        query_vector = consolidator._get_embedding(query_text)
        if not query_vector:
            print("[-] Failed to generate embedding vector for recall query.")
            return
        matches = db.semantic_recall(query_vector=query_vector, limit=5, min_similarity=0.4)
        print(f"\n🧠 Vespera Semantic Memory Recall | Query: '{query_text}'")
        print("=" * 70)
        if not matches:
            print("[*] No matching facts found above threshold.")
        else:
            for i, r in enumerate(matches, 1):
                score_pct = int(r["similarity"] * 100)
                tag = f" [{r['project_tag']}]" if r.get("project_tag") else ""
                print(f"[{i}] [Match: {score_pct}% | Category: {r['category'].upper()}{tag}]\n    {r['fact']}\n")
        print("=" * 70)
        return

    if args.command == "get-context":
        limit = 10
        context = db.get_recent_context(limit=limit)
        if not context:
            print("[-] No recent context found in memory database.")
            return
        print(f"[+] Recent Context Window ({len(context)} messages):\n")
        for session_id, role, content, created_at in context:
            tag = "👤 Pilot" if role in ["Pilot", "user", "USER_INPUT"] else "🤖 Vespera"
            preview = content[:200].replace("\n", " ") if content else ""
            print(f"  [{created_at}] {tag}: {preview}...")
        
        # Also output top facts
        facts = db.get_facts(limit=10)
        if facts:
            print(f"\n[+] Top {len(facts)} Active Facts:")
            for f in facts:
                print(f"  • ({f['category']}, conf={f['confidence']:.2f}) {f['fact'][:100]}")
        return

    if args.command == "webui":
        from web_server import run_server
        run_server(port=8890)

    elif args.command == "tui":
        from tui.dashboard import ULMTUIDashboard
        app = ULMTUIDashboard()
        app.start()

    elif args.command == "daemon":
        from core.daemon import ULMDaemon
        daemon = ULMDaemon()
        daemon.start()

    elif args.command == "sync":
        async def run_sync():
            print(f"\n[*] ULM Pipeline Initialized | Parser: {args.parser.upper()} | Injector: {args.injector.upper()}")
            
            parser_class = PARSERS[args.parser]
            log_parser = parser_class(llm_model=args.llm_model, vector_model=args.vector_model)
            new_logs = log_parser.fetch_new_logs()
            
            if new_logs:
                if not args.dry_run:
                    db.import_raw_logs(new_logs)
                    print(f"[+] ETL Complete: Ingested {len(new_logs)} session modifications.")
            else:
                print("[*] No new logs detected.")

            if not args.dry_run:
                # Evaluate new sessions asynchronously
                try:
                    from core.profile_evaluator import ProfileEvaluator
                    evaluator = ProfileEvaluator()
                    unprofiled = db.get_unprofiled_sessions()
                    if unprofiled:
                        print(f"[*] Running developer profile evaluation on {len(unprofiled)} sessions...")
                        
                        # Create a worker pool to process sessions in parallel
                        async def worker(queue):
                            while not queue.empty():
                                s_id = await queue.get()
                                try:
                                    if await evaluator.evaluate_session(db, s_id):
                                        db.mark_session_profiled(s_id)
                                except Exception as e:
                                    print(f"[-] Profile evaluation failed for session {s_id[:8]}: {e}")
                                finally:
                                    queue.task_done()

                        queue = asyncio.Queue()
                        for s_id in unprofiled:
                            queue.put_nowait(s_id)
                        
                        # Run 4 workers in parallel (adjustable based on LLM capacity)
                        workers = [asyncio.create_task(worker(queue)) for _ in range(4)]
                        await asyncio.gather(*workers)
                        await queue.join()
                    
                    await evaluator.close()
                except Exception as e:
                    print(f"[-] Profile evaluation failed: {e}")

                # Run memory consolidator to resolve fact conflicts
                try:
                    from core.consolidator import MemoryConsolidator
                    consolidator = MemoryConsolidator(db)
                    consolidator.consolidate()
                except Exception as e:
                    print(f"[-] Fact consolidation failed: {e}")

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
            # Purge VRAM and terminate Ollama after sync pipeline completes
            try:
                from core.utils import shutdown_ollama
                ollama_endpoint = db.get_preference("ollama_endpoint", "http://localhost:11434")
                shutdown_ollama(endpoint=ollama_endpoint)
            except Exception as e:
                print(f"[-] Ollama shutdown error: {e}")

        # Execute the async sync process
        asyncio.run(run_sync())

if __name__ == "__main__":
    main()