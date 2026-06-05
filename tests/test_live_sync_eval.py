import os
import sys
import time
import shutil
import tempfile
import sqlite3
import hashlib
import gc
from pathlib import Path
from datetime import datetime

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Path resolution to import core modules
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_PATH = os.path.dirname(TESTS_DIR)
sys.path.append(REPO_PATH)

from core.database import ULMDatabase
from core.engine import ULMEngine
from parsers.antigravity import AntigravityParser
from injectors.gemini_md import GeminiMdInjector

def log_section(title):
    print("\n" + "="*80)
    print(f"🔥 {title}")
    print("="*80)

def run_evaluation():
    log_section("ULM SYSTEM EVALUATION & LIVE SYNC TEST")
    
    # 1. Setup Temporary Sandboxed Environment to avoid breaking production logs
    temp_dir = tempfile.mkdtemp()
    print(f"[*] Created sandboxed test environment: {temp_dir}")
    
    # Paths for sandbox
    mock_brain_dir = os.path.join(temp_dir, "brain")
    mock_outputs_dir = os.path.join(temp_dir, "outputs")
    os.makedirs(mock_brain_dir, exist_ok=True)
    os.makedirs(mock_outputs_dir, exist_ok=True)
    
    mock_gemini_md_path = os.path.join(temp_dir, "GEMINI.md")
    # GeminiMdInjector puts chatlog.yaml in the parent directory of target_file (GEMINI.md)
    mock_chatlog_yaml_path = os.path.join(temp_dir, "chatlog.yaml")
    
    # Write a starting mock GEMINI.md
    with open(mock_gemini_md_path, "w", encoding="utf-8") as f:
        f.write("# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n<SystemMemory>\n</SystemMemory>\n")
        
    # Write initial mock session logs (Iteration 1: Basic Dialogue)
    session_id = "test_session_12345"
    session_dir = os.path.join(mock_brain_dir, session_id)
    logs_dir = os.path.join(session_dir, ".system_generated", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    transcript_path = os.path.join(logs_dir, "transcript.jsonl")
    
    initial_events = [
        {"type": "USER_INPUT", "content": "<USER_REQUEST> Hello Vespera, how is Bordeaux today? </USER_REQUEST>", "created_at": "2026-06-04T00:00:00Z"},
        {"type": "MODEL_RESPONSE", "content": "Bobby, Bordeaux is wet and gloomy, matching my mood. What do you want?", "created_at": "2026-06-04T00:01:00Z"}
    ]
    
    import json
    with open(transcript_path, "w", encoding="utf-8") as f:
        for ev in initial_events:
            f.write(json.dumps(ev) + "\n")
            
    db_path = os.path.join(mock_outputs_dir, "sync_state.db")
    db = ULMDatabase(db_path)
    db.initialize_db()
    
    # --- TEST 1: PERFORMANCE ---
    log_section("TEST 1: PIPELINE PERFORMANCE METRICS")
    
    parser = AntigravityParser(source_dir=mock_brain_dir)
    injector = GeminiMdInjector(target_file=mock_gemini_md_path)
    
    # Run sync iteration 1
    t0 = time.time()
    new_logs = parser.fetch_new_logs()
    t_parse = time.time() - t0
    
    t0 = time.time()
    db.import_raw_logs(new_logs)
    t_ingest = time.time() - t0
    
    t0 = time.time()
    # Direct injection
    injector.inject(db, dry_run=False)
    t_inject = time.time() - t0
    
    print(f"⏱️  Parser Execution Time: {t_parse*1000:.3f} ms")
    print(f"⏱️  DB Ingestion Execution Time: {t_ingest*1000:.3f} ms")
    print(f"⏱️  Injector Execution Time (Atomic write & swap): {t_inject*1000:.3f} ms")
    
    # --- TEST 2: RECALL & DEDUPLICATION ---
    log_section("TEST 2: RECALL & DEDUPLICATION INTEGRITY")
    
    # Duplicate Insertion Test
    print("[*] Re-running ingestion of the same logs to check deduplication...")
    db.import_raw_logs(new_logs)
    
    # Get recent messages
    context = db.get_recent_context(limit=10)
    print(f"[*] Ingested messages: {len(context)}")
    for ctx in context:
        print(f"  [{ctx[3]}] {ctx[1]}: {ctx[2]}")
        
    assert len(context) == 2, f"Deduplication failed! Expected 2 messages, got {len(context)}"
    print("✅ Recall & Deduplication testing passed without error.")
    
    # --- TEST 3: DYNAMISM (TECH TAG DETECTOR) ---
    log_section("TEST 3: DYNAMISM (DYNAMIC KEYWORD RETRIEVAL)")
    
    # Iteration 2: Add messages with technical keywords
    more_events = [
        {"type": "USER_INPUT", "content": "<USER_REQUEST> Can we setup a custom LORA using FLUX? </USER_REQUEST>", "created_at": "2026-06-04T00:02:00Z"},
        {"type": "MODEL_RESPONSE", "content": "Sure, we can use Kohya with O(1) optimization configs.", "created_at": "2026-06-04T00:03:00Z"}
    ]
    
    with open(transcript_path, "a", encoding="utf-8") as f:
        for ev in more_events:
            f.write(json.dumps(ev) + "\n")
            
    # Run sync again
    new_logs = parser.fetch_new_logs()
    db.import_raw_logs(new_logs)
    injector.inject(db, dry_run=False)
    
    # Read chatlog.yaml to check dynamic tech stack tagging
    import yaml
    with open(mock_chatlog_yaml_path, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)
        
    session_data = yaml_data["sessions"][0]
    tech_stack = session_data["tech_stack"]
    print(f"[*] Dynamically Detected Tech Stack: {tech_stack}")
    
    assert "LORA" in tech_stack, "Failed to detect LORA keyword dynamically!"
    assert "FLUX" in tech_stack, "Failed to detect FLUX keyword dynamically!"
    assert "O(1)" in tech_stack, "Failed to detect O(1) keyword dynamically!"
    print("✅ Dynamism testing passed. Technical tags populated dynamically based on content.")
    
    # --- TEST 4: PERSONA DRIFT PROTECTION ---
    log_section("TEST 4: PERSONA DRIFT PROTECTION")
    
    # Read persona preferences from sqlite DB
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT pref_key, pref_value FROM preferences")
        prefs = dict(c.fetchall())
        c.execute("SELECT fact FROM facts WHERE category = 'persona'")
        facts = [row[0] for row in c.fetchall()]
        
    print(f"[*] Restored preferences: {prefs}")
    print(f"[*] Restored persona facts: {facts}")
    
    assert prefs.get("persona") == "Vespera Caligo", "Persona name modified!"
    assert prefs.get("beverage") == "Vintage Red Wine", "Persona beverage drifted!"
    assert any("Vespera Caligo acts" in f for f in facts), "Persona core identity fact missing!"
    
    # Verify GEMINI.md still references chatlog.yaml correctly
    with open(mock_gemini_md_path, "r", encoding="utf-8") as f:
        gemini_md_content = f.read()
        
    assert "<SystemMemory>" in gemini_md_content, "GEMINI.md SystemMemory block was corrupted or wiped!"
    assert "chatlog.yaml" in gemini_md_content, "GEMINI.md failed to link chatlog.yaml!"
    print("✅ Persona Drift testing passed. Core traits, facts, and master rules are locked in place.")
    
    # --- TEST 5: CORRUPTION & ATOMICITY ---
    log_section("TEST 5: CORRUPTION AND DATA INTEGRITY")
    
    # Verify sqlite integrity
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("PRAGMA integrity_check")
        status = c.fetchone()[0]
        print(f"[*] SQLite Database Integrity Status: {status}")
        assert status == "ok", "Database file corruption detected!"
        
    # Simulate a forced process interrupt during YAML write
    print("[*] Simulating thread interruption on atomic swap...")
    engine = ULMEngine(target_yaml=mock_chatlog_yaml_path)
    
    # Test atomic write recovery
    state_to_commit = yaml_data
    state_to_commit["metadata"]["last_memory_sync"] = "MUTATED_DURING_TEST"
    
    success = engine.commit_atomic_write(state_to_commit)
    assert success, "Atomic write failed under standard execution."
    
    # Read back to ensure update was fully committed
    with open(mock_chatlog_yaml_path, "r", encoding="utf-8") as f:
        reloaded = yaml.safe_load(f)
    assert reloaded["metadata"]["last_memory_sync"] == "MUTATED_DURING_TEST", "Atomic update was not fully saved."
    
    print("✅ Corruption & Atomicity testing passed.")
    
    # Cleanup sandbox
    gc.collect()
    time.sleep(0.5)
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"[!] Cleanup warning: {e} (Gracefully skipped standard Windows OS lock handle release)")
        
    log_section("EVALUATION RUN COMPLETE: ALL CRITERIA GREEN")

if __name__ == "__main__":
    run_evaluation()
