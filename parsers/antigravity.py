import os
import json
import chromadb
from datetime import datetime
from pathlib import Path
from parsers.base import BaseParser
from core import fact_extractor
from normalizers.adapters import GeminiNormalizer, AntigravityNormalizer

LAST_SYNC_FILE = Path(__file__).resolve().parents[1] / "core" / "last_sync.txt"

class AntigravityParser(BaseParser):
    def __init__(self, source_dirs, llm_model=None, vector_model=None):
        if not source_dirs:
            raise ValueError("source_dirs list must be provided")
        self.source_dirs = source_dirs if isinstance(source_dirs, list) else [source_dirs]
        self.llm_model = llm_model
        self.vector_model = vector_model        

    def _load_last_sync_timestamp(self):
        try:
            if LAST_SYNC_FILE.exists():
                raw = LAST_SYNC_FILE.read_text(encoding="utf-8").strip()
                if raw:
                    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            pass
        return None

    def _update_last_sync_timestamp(self):
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            LAST_SYNC_FILE.write_text(now_str, encoding="utf-8")
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
                
                # Logic: If directory, look for standard log structure. If file, treat as direct export.
                if os.path.isdir(full_path):
                    transcript_path = os.path.join(full_path, ".system_generated", "logs", "transcript.jsonl")
                    adapter = AntigravityNormalizer()
                else:
                    transcript_path = full_path
                    adapter = GeminiNormalizer()
                
                if os.path.exists(transcript_path):
                    mtime = os.path.getmtime(transcript_path)
                    if not force_ingest and last_sync_ts is not None and mtime <= last_sync_ts:
                        continue
                    
                    print(f"[+] Found session/file: {item}")
                    with open(transcript_path, 'r', encoding='utf-8') as f:
                        messages = adapter.parse(f.read())
                    
                    if messages:
                        extracted_payloads.append({
                            "chat_id": item,
                            "messages": messages
                        })
        
        if extracted_payloads:
            self._update_last_sync_timestamp()
        return extracted_payloads

    def ingest_payloads(self, extracted_payloads, llm_model):
        if not extracted_payloads:
            print("[*] No new payloads to ingest.")
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
    TARGET_MODEL = "qwen2.5-coder:14b"
    
    print(f"\n[INIT] Starting Pipeline at {TARGET_LOG_DIR}")
    parser = AntigravityParser(source_dirs=[TARGET_LOG_DIR], llm_model=TARGET_MODEL)
    
    # 1. Fetch
    payloads = parser.fetch_new_logs(force_ingest=True)
    
    # 2. Ingest
    parser.ingest_payloads(extracted_payloads=payloads, llm_model=TARGET_MODEL)
    
    print("\n[SUCCESS] Pipeline complete.")