import os
import sys
import sqlite3
import re
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.persona_evaluator import PersonaEvaluator

CONVERSATIONS_DIR = r"C:\Users\boben\.gemini\antigravity\conversations"
SYNC_DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\sync_state.db"

# Noise patterns to strip out terminal/system execution noise
NOISE_PATTERNS = [
    r"^command\(",
    r"^read_file\(",
    r"^write_file\(",
    r"^read_url\(",
    r"^\.venv\\Scripts",
    r"^Get-ChildItem",
    r"^Stop-Process",
    r"^Start-Sleep",
    r"^nvidia-smi",
    r"^ollama",
    r"^git ",
    r"^pip ",
    r"^python ",
    r"^C:\\Users\\",
    r"^D:\\AI\\"
]

def is_dialogue_line(text):
    """
    Filters out raw powershell/terminal commands and system paths.
    Returns True if the text looks like actual human/AI chat conversation.
    """
    if len(text) < 10:
        return False
        
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False
            
    return True

def extract_strings_from_blob(blob_data, min_length=15):
    if not blob_data or not isinstance(blob_data, bytes):
        return []
    
    pattern = re.compile(rb'[\x20-\x7e\n\r\t]{' + str(min_length).encode() + rb',}')
    matches = pattern.findall(blob_data)
    
    cleaned_strings = []
    for match in matches:
        try:
            text = match.decode('utf-8', errors='ignore').strip()
            if is_dialogue_line(text):
                cleaned_strings.append(text)
        except Exception:
            continue
            
    return cleaned_strings

def extract_text_from_db(db_path):
    extracted_text = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT step_payload, render_info, metadata FROM steps WHERE step_payload IS NOT NULL")
        for row in cursor.fetchall():
            for blob in row:
                if blob:
                    extracted_text.extend(extract_strings_from_blob(blob))

        cursor.execute("SELECT data FROM gen_metadata WHERE data IS NOT NULL")
        for row in cursor.fetchall():
            if row[0]:
                extracted_text.extend(extract_strings_from_blob(row[0]))

        conn.close()
    except Exception as e:
        print(f"[-] Error reading {os.path.basename(db_path)}: {e}")

    seen = set()
    unique_text = []
    for line in extracted_text:
        if line not in seen:
            seen.add(line)
            unique_text.append(line)

    return unique_text

def update_vespera_memory(traits, db_filename):
    if not traits:
        return 0
    try:
        conn = sqlite3.connect(SYNC_DB_PATH)
        cursor = conn.cursor()
        inserted = 0
        for t in traits:
            if not isinstance(t, dict):
                continue
            
            category = t.get("category", "lore").lower()
            trait = t.get("trait", "")
            confidence = float(t.get("confidence", 0.8))
            if not trait:
                continue
            
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
        print(f"[-] Database insertion choke for {db_filename}: {e}")
        return 0

def run_db_sweep():
    print("[*] Launching Deep Database Persona Sweep on Antigravity v2 conversations...")
    
    if not os.path.exists(CONVERSATIONS_DIR):
        print(f"[!] Conversations directory not found at {CONVERSATIONS_DIR}")
        return

    db_files = [
        f for f in os.listdir(CONVERSATIONS_DIR) 
        if f.endswith(".db") and not f.endswith("-shm") and not f.endswith("-wal")
    ]
    
    db_paths = [
        (f, os.path.join(CONVERSATIONS_DIR, f), os.path.getmtime(os.path.join(CONVERSATIONS_DIR, f)))
        for f in db_files
    ]
    db_paths.sort(key=lambda x: x[2], reverse=True)

    print(f"[*] Found {len(db_paths)} conversation databases. Initializing evaluator...")
    evaluator = PersonaEvaluator()
    total_traits = 0
    start_time = time.time()

    for idx, (filename, full_path, mtime) in enumerate(db_paths, 1):
        print(f"\n[{idx}/{len(db_paths)}] Extracting from {filename}...")
        raw_lines = extract_text_from_db(full_path)
        
        if not raw_lines:
            print("    [-] No readable dialogue text found in database.")
            continue
            
        # Take the top 100 actual dialogue lines rather than a raw character slice
        dialogue_sample = "\n".join(raw_lines[:100])
        print(f"    [*] Extracted {len(raw_lines)} dialogue blocks. Feeding sample to Vespera...")
        print(f"    [SAMPLE DIALOGUE SENT TO LLM]:\n    {dialogue_sample[:250]}...\n")
        
        traits = evaluator.evaluate_chunk(dialogue_sample)
        print(f"    [DEBUG RAW TRAITS RETURNED]: {traits}")
        
        if traits:
            inserted = update_vespera_memory(traits, filename)
            total_traits += inserted
            print(f"    [+] Bingo! Extracted {inserted} persona traits.")
            for t in traits:
                if isinstance(t, dict):
                    print(f"        -> [{t.get('category', 'LORE').upper()}]: {t.get('trait', '')}")
        else:
            print("    [-] Empty or no traits found. Skipped.")

    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print(f"[+] DEEP DB SWEEP COMPLETE in {elapsed} seconds.")
    print(f"[+] Total new persona traits committed: {total_traits}")
    print("=" * 80)

if __name__ == "__main__":
    run_db_sweep()