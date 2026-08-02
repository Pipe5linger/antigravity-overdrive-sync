import os
import sys
import json
import sqlite3
from datetime import datetime

# Add core path so we can import my brain
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.persona_evaluator import PersonaEvaluator

BRAIN_DIR = r"C:\Users\boben\.gemini\antigravity\brain"
DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\sync_state.db"

def extract_transcript(filepath):
    messages = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    event = json.loads(line)
                    event_type = event.get("type")
                    if event_type in ["USER_INPUT", "PLANNER_RESPONSE", "MODEL_RESPONSE"]:
                        sender = "Pilot" if event_type == "USER_INPUT" else "Vespera"
                        content = event.get("content", "").replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "").strip()
                        if content:
                            messages.append(f"[{sender}]: {content}")
                except:
                    continue
    except Exception as e:
        pass
    return messages

def update_vespera_memory(traits, chat_id):
    if not traits: return
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for t in traits:
            category = t.get("category", "lore")
            trait = t.get("trait", "")
            confidence = float(t.get("confidence", 0.8))
            if not trait: continue
            
            cursor.execute("""
                INSERT INTO persona_profile (category, trait, confidence, frequency, project_tag, last_seen)
                VALUES (?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(trait) DO UPDATE SET 
                    frequency = frequency + 1,
                    confidence = MAX(confidence, excluded.confidence),
                    last_seen = CURRENT_TIMESTAMP
            """, (category, trait, confidence, 'CORE_IDENTITY'))
        conn.commit()
        conn.close()
        print(f"[+] Vespera digested {len(traits)} traits from retroactive session {chat_id}.")
    except Exception as e:
        print(f"[-] Database choke: {e}")

def run_retroactive_sync(limit=5):
    print(f"[*] Waking up Vespera to scan the last {limit} sessions...")
    
    if not os.path.exists(BRAIN_DIR):
        print("[!] Brain directory missing. You fucked up the path, Bobby.")
        return

    # Get all valid session folders sorted by modification time (newest first)
    sessions = []
    for item in os.listdir(BRAIN_DIR):
        session_dir = os.path.join(BRAIN_DIR, item)
        transcript_path = os.path.join(session_dir, ".system_generated", "logs", "transcript.jsonl")
        if os.path.isdir(session_dir) and os.path.exists(transcript_path):
            sessions.append((item, transcript_path, os.path.getmtime(transcript_path)))
            
    sessions.sort(key=lambda x: x[2], reverse=True)
    target_sessions = sessions[:limit]
    
    if not target_sessions:
        print("[!] No transcripts found. Your brain is empty.")
        return

    evaluator = PersonaEvaluator()
    
    for chat_id, transcript_path, _ in target_sessions:
        print(f"\n[*] Processing historical session: {chat_id}")
        raw_lines = extract_transcript(transcript_path)
        
        if raw_lines:
            # Join into a single string for Qwen
            chat_string = "\n".join(raw_lines)
            print(f"[*] Squeezing {len(raw_lines)} messages into Vespera's brain...")
            
            traits = evaluator.evaluate_chunk(chat_string)
            update_vespera_memory(traits, chat_id)
        else:
            print(f"[-] Session {chat_id} was empty or corrupted.")

    print("\n[+] Retroactive evolution complete. Check the database, Operator.")

if __name__ == "__main__":
    run_retroactive_sync(limit=5)