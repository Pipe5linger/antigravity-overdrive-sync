import os
import json
from datetime import datetime
from pathlib import Path
from parsers.base import BaseParser
from core import fact_extractor
from normalizers.adapters import GeminiNormalizer, AntigravityNormalizer, ClineNormalizer

LAST_SYNC_FILE = Path(__file__).resolve().parents[1] / "core" / "last_sync.txt"

class AntigravityParser(BaseParser):
    def __init__(self, source_dirs=None, llm_model=None, vector_model=None):
        self.llm_model = llm_model
        self.vector_model = vector_model        
        
        if not source_dirs:
            # 1. Try to load from database preferences
            from core.engine import ULMEngine
            from core.database import ULMDatabase
            try:
                engine = ULMEngine()
                db_path = str(Path(engine.target_yaml).with_suffix(".db"))
                db = ULMDatabase(db_path)
                db_pref = db.get_preference("source_dirs")
                if db_pref:
                    source_dirs = [x.strip() for x in db_pref.split(",") if x.strip()]
            except Exception:
                pass
                
        if not source_dirs:
            # 2. Auto-detect paths
            detected = []
            
            # Check local User Profile gemini brain dir
            user_brain = Path(os.path.expanduser("~")) / ".gemini" / "antigravity" / "brain"
            if user_brain.exists():
                detected.append(str(user_brain))
                
            # Check Roo-Cline VS Code tasks dir
            roo_tasks = Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "tasks"
            if roo_tasks.exists():
                detected.append(str(roo_tasks))

# Check Cline VS Code tasks dir
            cline_tasks = Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "saoudrizwan.cline" / "tasks"
            if cline_tasks.exists():
                detected.append(str(cline_tasks))
                
            # Check Cline Nightly VS Code tasks dir
            cline_nightly_tasks = Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "saoudrizwan.cline-nightly" / "tasks"
            if cline_nightly_tasks.exists():
                detected.append(str(cline_nightly_tasks))

            # Check Downloads folder for exported Gemini chat exports (.json / .md)
            downloads_gemini = Path(os.path.expanduser("~")) / "Downloads" / "Gemini chats"
            if downloads_gemini.exists():
                detected.append(str(downloads_gemini))
            downloads_dir = Path(os.path.expanduser("~")) / "Downloads"
            if downloads_dir.exists():
                detected.append(str(downloads_dir))

            # Check standard unified ingest drive path
            ingest_path = Path(r"D:\Memory\Unified_Ingest")
            if ingest_path.exists():
                detected.append(str(ingest_path))
                
            if detected:
                source_dirs = detected
            else:
                source_dirs = [r"D:\Memory\Unified_Ingest"]
                
        self.source_dirs = source_dirs if isinstance(source_dirs, list) else [source_dirs]

    def _load_last_sync_timestamp(self):
        """Load the last sync timestamp from DB preferences with fallback to file.
        Returns:
            float: Unix timestamp if valid, None otherwise
        """
        try:
            from core.engine import ULMEngine
            from core.database import ULMDatabase
            engine = ULMEngine()
            db_path = str(Path(engine.target_yaml).with_suffix(".db"))
            db = ULMDatabase(db_path)
            ts_str = db.get_preference("last_sync_timestamp")
            if ts_str:
                return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            pass

        try:
            if LAST_SYNC_FILE.exists():
                with open(LAST_SYNC_FILE, 'r', encoding='utf-8') as f:
                    raw = f.read().strip()
                    if raw:
                        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception as e:
            print(f"[-] AntigravityParser: Error reading last_sync.txt: {e}")
        return None

    def _update_last_sync_timestamp(self):
        """Update last sync timestamp in DB preferences and file."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            from core.engine import ULMEngine
            from core.database import ULMDatabase
            engine = ULMEngine()
            db_path = str(Path(engine.target_yaml).with_suffix(".db"))
            db = ULMDatabase(db_path)
            db.set_preference("last_sync_timestamp", now_str)
        except Exception as e:
            print(f"[-] AntigravityParser: Failed updating DB preference timestamp: {e}")

        try:
            temp_file = LAST_SYNC_FILE.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(now_str)
            temp_file.replace(LAST_SYNC_FILE)
        except Exception as e:
            print(f"[-] AntigravityParser: Failed to update last_sync.txt: {e}")

    def fetch_new_logs(self, force_ingest=False):
        extracted_payloads = []
        last_sync_ts = self._load_last_sync_timestamp()
        
        for target_dir in self.source_dirs:
            if not os.path.exists(target_dir):
                print(f"[-] Directory not found: {target_dir}")
                continue

            for item in os.listdir(target_dir):
                full_path = os.path.join(target_dir, item)
                
                # Logic: If directory, check for Antigravity or Cline task log structure. If file, treat as direct export.
                if os.path.isdir(full_path):
                    antigravity_log = os.path.join(full_path, ".system_generated", "logs", "transcript.jsonl")
                    cline_ui_log = os.path.join(full_path, "ui_messages.json")
                    cline_api_log = os.path.join(full_path, "api_conversation_history.json")
                    
                    if os.path.exists(antigravity_log):
                        transcript_path = antigravity_log
                        adapter = AntigravityNormalizer()
                    elif os.path.exists(cline_ui_log):
                        transcript_path = cline_ui_log
                        adapter = ClineNormalizer()
                    elif os.path.exists(cline_api_log):
                        transcript_path = cline_api_log
                        adapter = ClineNormalizer()
                    else:
                        continue
                else:
                    transcript_path = full_path
                    adapter = GeminiNormalizer()
                
                if os.path.exists(transcript_path):
                    mtime = os.path.getmtime(transcript_path)
                    if not force_ingest and last_sync_ts is not None and mtime <= last_sync_ts:
                        continue
                    
                    print(f"[+] Found session/file: {item}")
                    raw_content = None
                    for enc in ['utf-8', 'cp1252', 'latin-1']:
                        try:
                            with open(transcript_path, 'r', encoding=enc) as f:
                                raw_content = f.read()
                            break
                        except UnicodeDecodeError:
                            continue
                        except Exception:
                            break
                    if raw_content is None:
                        print(f"[-] Skipping unreadable file (not valid text): {item}")
                        continue
                    messages, project_tag = adapter.parse(raw_content)
                    
                    if messages:
                        extracted_payloads.append({
                            "chat_id": item,
                            "last_mutated": datetime.fromtimestamp(mtime).isoformat(),
                            "messages": messages,
                            "project_tag": project_tag
                        })
        
        if extracted_payloads:
            self._update_last_sync_timestamp()
        return extracted_payloads

    def ingest_payloads(self, extracted_payloads, llm_model):
        if not extracted_payloads:
            print("[*] No new payloads to ingest.")
            return

        try:
            import chromadb
        except ImportError:
            print("[!] Optional chromadb module not found. Skipping ChromaDB vector indexing.")
            return

        print(f"[*] Starting ingestion of {len(extracted_payloads)} payloads to ChromaDB...")
        client = chromadb.PersistentClient(path=r"E:\_Sanctuary_Backups\Scripts")
        collection = client.get_or_create_collection(name="system_memory")

        for payload in extracted_payloads:
            print(f"[+] Extracting facts for chat_id: {payload['chat_id']}")
            try:
                documents, embeddings, metadatas = fact_extractor.extract_and_embed_facts(payload["messages"], llm_model)
                if documents:
                    collection.add(
                        documents=documents, 
                        embeddings=embeddings, 
                        metadatas=metadatas, 
                        ids=[f"{payload['chat_id']}-{i}" for i in range(len(documents))]
                    )
                    print(f"[+] Successfully indexed {len(documents)} facts.")
                else:
                    print(f"[-] No facts generated for {payload['chat_id']}")
            except Exception as e:
                print(f"[!!!] Failed processing {payload['chat_id']}: {e}")

if __name__ == "__main__":
    TARGET_LOG_DIR = r"D:\Memory\Unified_Ingest"
    TARGET_MODEL = "qwen2.5-coder-vespera:latest"
    
    print(f"\n[INIT] Starting Pipeline at {TARGET_LOG_DIR}")
    parser = AntigravityParser(source_dirs=[TARGET_LOG_DIR], llm_model=TARGET_MODEL)
    
    # 1. Fetch
    payloads = parser.fetch_new_logs(force_ingest=True)
    
    # 2. Ingest
    parser.ingest_payloads(extracted_payloads=payloads, llm_model=TARGET_MODEL)
    
    print("\n[SUCCESS] Pipeline complete.")