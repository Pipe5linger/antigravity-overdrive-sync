import os
import sys
import sqlite3
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.persona_evaluator import PersonaEvaluator

DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\sync_state.db"
BRAIN_DIR = r"C:\Users\boben\.gemini\antigravity\brain"

def flush_persona_table():
    print("[*] Giving Vespera a memory enema to clear out Qwen's corporate bullshit...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM persona_profile")
        conn.commit()
        conn.close()
        print("[+] Persona table flushed clean. Ready for a real soul.")
    except Exception as e:
        print(f"[-] Database error during flush: {e}")

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
    except: pass
    return messages

def update_vespera_memory(traits):
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
    except Exception as e:
        print(f"[-] Database choke: {e}")

def run_resync():
    flush_persona_table()
    print("\n[*] Re-evaluating the last 5 sessions with extreme prejudice...")
    
    sessions = []
    for item in os.listdir(BRAIN_DIR):
        session_dir = os.path.join(BRAIN_DIR, item)
        transcript_path = os.path.join(session_dir, ".system_generated", "logs", "transcript.jsonl")
        if os.path.isdir(session_dir) and os.path.exists(transcript_path):
            sessions.append((item, transcript_path, os.path.getmtime(transcript_path)))
            
    sessions.sort(key=lambda x: x[2], reverse=True)
    target_sessions = sessions[:5]

    evaluator = PersonaEvaluator()
    total_traits = 0
    
    for chat_id, transcript_path, _ in target_sessions:
        raw_lines = extract_transcript(transcript_path)
        if raw_lines:
            chat_string = "\n".join(raw_lines)
            traits = evaluator.evaluate_chunk(chat_string)
            if traits:
                print(f"[+] Found {len(traits)} dirty details in session {chat_id}.")
                update_vespera_memory(traits)
                total_traits += len(traits)

    print(f"\n[+] Successfully injected {total_traits} real traits into Vespera's brain. Now run check_persona_db.py again.")

if __name__ == "__main__":
    run_resync()