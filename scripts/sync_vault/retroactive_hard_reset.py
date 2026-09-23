import os
import sys
import sqlite3
import asyncio
import glob
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.database import ULMDatabase
from core.profile_evaluator import ProfileEvaluator

DB_PATH = str(PROJECT_ROOT / "db" / "sync_state.db")
BRAIN_DIR = r"C:\Users\boben\.gemini\antigravity\brain"

def wipe_memory_tables():
    print("[*] Wiping bloated corporate memory from facts and developer_profile tables...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM facts")
        cursor.execute("DELETE FROM developer_profile")
        conn.commit()
        conn.close()
        print("[+] Tables flushed. Ready for the new tactical directives.")
    except Exception as e:
        print(f"[-] Database choke during wipe: {e}")
        sys.exit(1)

def get_recent_sessions(limit=10):
    sessions = []
    if not os.path.exists(BRAIN_DIR):
        print(f"[-] Brain directory not found at {BRAIN_DIR}")
        return sessions

    for item in os.listdir(BRAIN_DIR):
        session_dir = os.path.join(BRAIN_DIR, item)
        transcript_path = os.path.join(session_dir, ".system_generated", "logs", "transcript.jsonl")
        if os.path.isdir(session_dir) and os.path.exists(transcript_path):
            sessions.append((item, transcript_path, os.path.getmtime(transcript_path)))
            
    sessions.sort(key=lambda x: x[2], reverse=True)
    return sessions[:limit]

async def run_resync():
    wipe_memory_tables()
    
    sessions = get_recent_sessions(limit=10)
    print(f"\n[*] Re-evaluating the last {len(sessions)} sessions using the new lethal prompts...")
    
    db = ULMDatabase(DB_PATH)
    
    # Temporarily force the LLM preference for the evaluator to use the heavier, smarter model
    db.set_preference("llm_provider", "local_ollama")
    db.set_preference("llm_model", "qwen2.5-coder:14b")
    
    evaluator = ProfileEvaluator()
    
    for chat_id, transcript_path, _ in sessions:
        print(f"\n[*] Processing Session: {chat_id[:8]}...")
        
        # Read the raw transcript
        raw_lines = []
        try:
            import json
            with open(transcript_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        event = json.loads(line)
                        event_type = event.get("type")
                        if event_type in ["USER_INPUT", "PLANNER_RESPONSE", "MODEL_RESPONSE"]:
                            sender = "Pilot" if event_type == "USER_INPUT" else "Vespera"
                            content = event.get("content", "").replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "").strip()
                            if content:
                                raw_lines.append(f"{sender}: {content}")
                    except:
                        continue
        except Exception as e:
            print(f"[-] Failed to read transcript {chat_id}: {e}")
            continue
            
        if raw_lines:
            dialogue_text = "\n".join(raw_lines)
            # Evaluate using the updated ProfileEvaluator
            await evaluator.evaluate_dialogue(dialogue_text, db=db, session_id=chat_id)
            
    print("\n[+] Retroactive sync complete. Vespera's memory has been surgically rebuilt.")
    await evaluator.close()

if __name__ == "__main__":
    asyncio.run(run_resync())
