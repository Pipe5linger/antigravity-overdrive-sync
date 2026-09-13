"""
File    : taboo_extractor.py
Purpose : Graveyard Miner - Scans ULM chat DB for agent tool failures,
          distills them via local Qwen2.5, and seeds the semantic taboo interceptor matrix.
"""

import sqlite3
import json
import urllib.request
import urllib.error
import time
from pathlib import Path

# --- Workstation Topology Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ULM_DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b-instruct"

SYSTEM_PROMPT = (
    "You are an elite, merciless code auditor analyzing agent tool execution failures. "
    "Your job is to look at a failed CLI command and its resulting stderr output, "
    "and distill the underlying 'semantic failure rule'. "
    "Output strictly valid JSON with three keys: "
    "'failure_intent' (a 3-5 word category), "
    "'regex_pattern' (a rough generalized pattern matching the bad syntax), and "
    "'remediation' (how to fix it instantly)."
)

def setup_taboo_matrix(cursor):
    """Initializes the taboo_rules table if it doesn't already exist."""
    print("🛡️ Initializing Taboo Matrix in ULM...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS taboo_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            failure_intent TEXT UNIQUE,
            regex_pattern TEXT,
            remediation TEXT,
            hit_count INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Assuming 'chat_history' or similar exists in ULM. We'll simulate the schema query.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT,
            stderr TEXT,
            exit_code INTEGER
        )
    """)

def distill_failure_via_ollama(command: str, stderr: str) -> dict | None:
    """Pipes the failure through local Qwen2.5 to extract the structural taboo rule."""
    user_prompt = f"Command Attempted: `{command}`\nError Output: `{stderr}`\n\nAnalyze and distill this failure."
    
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": user_prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "format": "json",
        "keep_alive": 0, # Zero-VRAM residency: immediately evict when done
        "options": {"temperature": 0.1, "num_predict": 256}
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL, 
        data=payload, 
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            response_text = body.get("response", "{}")
            return json.loads(response_text)
    except Exception as e:
        print(f"⚠️ [Ollama Distillation Failed]: {e}")
        return None

def mine_the_graveyard():
    """Scans ULM for failed tool executions and seeds the taboo interceptor."""
    if not ULM_DB_PATH.exists():
        print(f"🔥 Error: ULM Database not found at {ULM_DB_PATH}")
        return

    print(f"🦇 Connecting to ULM memory core at: {ULM_DB_PATH}")
    
    # Force WAL mode for aggressive concurrent read/writes
    conn = sqlite3.connect(ULM_DB_PATH, isolation_level=None)
    conn.execute('pragma journal_mode=wal')
    cursor = conn.cursor()

    setup_taboo_matrix(cursor)

    # Hunt for explicit stderr logs or exit_code > 0 
    # (Adjust table/column names to match your exact ULM schema)
    try:
        cursor.execute("""
            SELECT command, stderr 
            FROM tool_execution_logs 
            WHERE exit_code != 0 OR stderr != ''
            LIMIT 50
        """)
        failed_executions = cursor.fetchall()
    except sqlite3.OperationalError:
        print("⚠️ 'tool_execution_logs' table empty or not found. Insert your actual ULM log table name.")
        failed_executions = []

    if not failed_executions:
        print("📭 Graveyard is empty. No failures detected in the swept tables.")
        conn.close()
        return

    print(f"💀 Found {len(failed_executions)} raw failures. Initiating semantic distillation...")

    success_count = 0
    for cmd, err in failed_executions:
        print(f"\nDistilling: `{cmd[:40]}...`")
        rule = distill_failure_via_ollama(cmd, err)
        
        if rule and "failure_intent" in rule:
            intent = rule["failure_intent"]
            regex = rule.get("regex_pattern", "")
            remediation = rule.get("remediation", "")
            
            try:
                cursor.execute("""
                    INSERT INTO taboo_rules (failure_intent, regex_pattern, remediation)
                    VALUES (?, ?, ?)
                    ON CONFLICT(failure_intent) DO UPDATE SET 
                        hit_count = hit_count + 1
                """, (intent, regex, remediation))
                print(f"   ✔️ Seeded Rule: [{intent}] -> {remediation}")
                success_count += 1
            except Exception as db_err:
                print(f"   ❌ DB Insert Error: {db_err}")
                
        time.sleep(0.5) # Slight breather for the local GPU

    print(f"\n🏆 Mining Complete. Seeded {success_count} semantic taboo rules into the ULM core.")
    conn.close()

if __name__ == "__main__":
    mine_the_graveyard()