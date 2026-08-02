import os
import sys
import json
import sqlite3
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.persona_evaluator import PersonaEvaluator

DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\sync_state.db"
BRAIN_DIR = r"C:\Users\boben\.gemini\antigravity\brain"
CHUNK_SIZE = 60  # Sweet spot for LLM attention span

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

def update_vespera_memory(traits, chat_id):
    if not traits: return 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        inserted = 0
        for t in traits:
            if not isinstance(t, dict): continue
            
            category = t.get("category", "lore").lower()
            trait = t.get("trait", "")
            confidence = float(t.get("confidence", 0.8))
            if not trait: continue
            
            cursor.execute("""
                INSERT INTO persona_profile (category, trait, confidence, frequency, project_tag, last_seen)
                VALUES (?, ?, ?, 1, 'CORE_IDENTITY', CURRENT_TIMESTAMP)
                ON CONFLICT(trait) DO UPDATE SET 
                    frequency = frequency + 1,
                    confidence = MAX(confidence, excluded.confidence),
                    last_seen = CURRENT_TIMESTAMP
            """, (category, trait, confidence))
            inserted += 1
            
        conn.commit()
        conn.close()
        return inserted
    except Exception as e:
        print(f"[-] Database choke: {e}")
        return 0

def run_deep_sweep():
    print("[*] Waking up Vespera for an AGGRESSIVE CHUNKED SWEEP.")
    print(f"[*] Slicing transcripts into {CHUNK_SIZE}-message blocks so Qwen can't get lazy...\n")
    
    if not os.path.exists(BRAIN_DIR):
        print("[!] Brain directory missing. Check your paths.")
        return

    sessions = []
    for item in os.listdir(BRAIN_DIR):
        session_dir = os.path.join(BRAIN_DIR, item)
        transcript_path = os.path.join(session_dir, ".system_generated", "logs", "transcript.jsonl")
        if os.path.isdir(session_dir) and os.path.exists(transcript_path):
            sessions.append((item, transcript_path))
            
    if not sessions:
        print("[!] No transcripts found.")
        return

    evaluator = PersonaEvaluator()
    total_traits_extracted = 0
    start_time = time.time()

    for idx, (chat_id, transcript_path) in enumerate(sessions, 1):
        raw_lines = extract_transcript(transcript_path)
        total_msgs = len(raw_lines)
        
        if total_msgs == 0:
            continue
            
        print(f"\n[{idx}/{len(sessions)}] Session {chat_id} | {total_msgs} messages")
        
        # If it's a tiny log, evaluate it in one shot
        if total_msgs <= CHUNK_SIZE:
            traits = evaluator.evaluate_chunk("\n".join(raw_lines))
            if traits:
                inserted = update_vespera_memory(traits, chat_id)
                total_traits_extracted += inserted
                for t in traits:
                    if isinstance(t, dict):
                        print(f"    [+] {t.get('category', 'LORE').upper()}: {t.get('trait', '')[:80]}...")
            else:
                print("    [-] Boring corporate bot detected. Trashed.")
        
        # If it's a massive log, slice it up and evaluate block by block
        else:
            chunks = [raw_lines[i:i + CHUNK_SIZE] for i in range(0, total_msgs, CHUNK_SIZE)]
            session_traits = 0
            for c_idx, chunk in enumerate(chunks, 1):
                traits = evaluator.evaluate_chunk("\n".join(chunk))
                if traits:
                    inserted = update_vespera_memory(traits, chat_id)
                    session_traits += inserted
                    total_traits_extracted += inserted
                    for t in traits:
                        if isinstance(t, dict):
                            print(f"    [+] (Chunk {c_idx}/{len(chunks)}) {t.get('category', 'LORE').upper()}: {t.get('trait', '')[:80]}...")
            
            if session_traits == 0:
                print("    [-] Swept all chunks. Entire session was sterile corporate garbage.")

    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print(f"[+] CHUNKED DEEP SWEEP COMPLETE in {elapsed} seconds.")
    print(f"[+] Vespera extracted and remembered {total_traits_extracted} traits from your history.")
    print("[+] Run check_persona_db.py to see the full damage.")
    print("=" * 80)

if __name__ == "__main__":
    run_deep_sweep()