"""
File    : taboo_extractor.py
Purpose : Graveyard Miner 2.0 - Hybrid Failure Interceptor & Taboo Matrix.
          1. Instant Deterministic Heuristic Classifier (0ms, 0 VRAM, handles known syntax/PATH/encoding errors).
          2. Procedural Graph Linkage (auto-routes failures to verified playbooks).
          3. Fallback Local LLM Distillation (Qwen2.5 only for novel/complex failures).
"""

import sys
import sqlite3
import json
import re
import urllib.request
import urllib.error
import time
from pathlib import Path

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except AttributeError:
        pass

# --- Workstation Topology Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ULM_DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:14b"

SYSTEM_PROMPT = (
    "You are an elite, merciless code auditor analyzing agent tool execution failures. "
    "Your job is to look at a failed CLI command and its resulting stderr output, "
    "and distill the underlying 'semantic failure rule'. "
    "If a provided Procedure from the graph solves this, suggest executing the target_script_path instead. "
    "Output strictly valid JSON with three keys: "
    "'failure_intent' (a 3-5 word category), "
    "'regex_pattern' (a rough generalized pattern matching the bad syntax), and "
    "'remediation' (how to fix it instantly or which procedure script to run)."
)

# --- Sanitization & Provenance Boundary ---
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")

def sanitize_identifier(raw: str) -> str | None:
    """Validates that an identifier extracted from error output is strictly alphanumeric/dashes/dots and <= 64 chars."""
    if not raw or not isinstance(raw, str):
        return None
    val = raw.strip()
    if SAFE_IDENTIFIER_PATTERN.match(val):
        return val
    return None

# --- Tier-2 Instant Deterministic Heuristics (0ms, Zero GPU Contention) ---
DETERMINISTIC_RULES = [
    {
        "pattern": r"The term '([^']+)' is not recognized",
        "intent": "Command Not Recognized",
        "regex": r"The term '(?P<cmd>[^']+)' is not recognized",
        "remediation_fn": lambda m, cmd, err, p: (
            f"Command '{sanitize_identifier(m.group(1))}' is not in Windows PATH. Ensure it is installed or use an existing procedural Python script."
            if sanitize_identifier(m.group(1))
            else "The specified command is not in Windows PATH. Ensure valid CLI syntax and verify environment PATH."
        )
    },
    {
        "pattern": r"SyntaxError: unterminated string literal",
        "intent": "PowerShell String Escaping SyntaxError",
        "regex": r"SyntaxError: unterminated string literal",
        "remediation_fn": lambda m, cmd, err, p: "Do not use python -c with escaped quotes in PowerShell. Always write a temporary .py scratch file instead."
    },
    {
        "pattern": r"ModuleNotFoundError: No module named '([^']+)'",
        "intent": "Python Module Import Failure",
        "regex": r"ModuleNotFoundError: No module named '(?P<mod>[^']+)'",
        "remediation_fn": lambda m, cmd, err, p: (
            f"Module '{sanitize_identifier(m.group(1))}' is missing from the active virtualenv. Run pip install {sanitize_identifier(m.group(1))} or check python sys.path."
            if sanitize_identifier(m.group(1))
            else "A required Python module is missing from the active virtualenv. Run pip install <module> or verify sys.path."
        )
    },
    {
        "pattern": r"UnicodeEncodeError: 'charmap' codec can't encode character",
        "intent": "Windows Charmap Encoding Error",
        "regex": r"UnicodeEncodeError: 'charmap' codec can't encode character",
        "remediation_fn": lambda m, cmd, err, p: "Windows console charmap encoding conflict. Enforce UTF-8 piping via sys.stdout.reconfigure(encoding='utf-8') or run vram_guard.py."
    },
    {
        "pattern": r"OutOfMemoryError: CUDA out of memory",
        "intent": "GPU VRAM Exhaustion",
        "regex": r"OutOfMemoryError: CUDA out of memory",
        "remediation_fn": lambda m, cmd, err, p: "RTX 4070 VRAM ceiling hit. Terminate background LLMs or run python scripts/generators_and_tools/vram_guard.py."
    },
    {
        "pattern": r"Array index expression is missing or not valid",
        "intent": "PowerShell Array Index Syntax Error",
        "regex": r"Array index expression is missing or not valid",
        "remediation_fn": lambda m, cmd, err, p: "PowerShell f-string array index collision. Avoid raw inline array indexing in terminal strings; use a dedicated .py script."
    },
    {
        "pattern": r"ValueError: not enough values to unpack \(expected (\d+), got (\d+)\)",
        "intent": "ValueError: Tuple Unpacking Mismatch",
        "regex": r"ValueError: not enough values to unpack",
        "remediation_fn": lambda m, cmd, err, p: "Unpacking signature mismatch. Verify return values or run python main.py sync --force."
    }
]

def setup_taboo_matrix(cursor):
    """Initializes the taboo_rules table if it doesn't already exist and ensures last_seen exists."""
    print("[*] Initializing Taboo Matrix in ULM...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS taboo_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            failure_intent TEXT UNIQUE,
            regex_pattern TEXT,
            remediation TEXT,
            hit_count INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE taboo_rules ADD COLUMN last_seen DATETIME DEFAULT CURRENT_TIMESTAMP")
    except sqlite3.OperationalError:
        pass


def retire_stale_taboos(cursor, max_age_days: int = 30) -> int:
    """Auto-retires stale taboo rules not observed within max_age_days to prevent prompt bloat."""
    try:
        cursor.execute("""
            DELETE FROM taboo_rules 
            WHERE last_seen < datetime('now', '-' || ? || ' days')
        """, (max_age_days,))
        pruned = cursor.rowcount
        if pruned > 0:
            print(f"[+] Taboo Matrix: Auto-retired {pruned} stale failure patterns (older than {max_age_days}d).")
        return pruned
    except Exception as e:
        print(f"[-] Taboo Matrix: Error retiring stale rules: {e}")
        return 0

def match_deterministic_heuristic(command: str, stderr: str, cursor) -> dict | None:
    """Fast-path classification: Evaluates stderr against deterministic patterns in 0.001ms."""
    combined = f"{command}\n{stderr}"
    for rule in DETERMINISTIC_RULES:
        match = re.search(rule["pattern"], combined, re.IGNORECASE)
        if match:
            # Query procedural graph playbooks to enrich remediation if applicable
            playbook_hint = ""
            try:
                cursor.execute("SELECT action_name, target_script_path FROM procedures WHERE action_name LIKE ? LIMIT 1", (f"%{rule['intent'][:10]}%",))
                row = cursor.fetchone()
                if row:
                    playbook_hint = f" Alternatively, trigger procedure '{row[0]}' via {row[1]}."
            except Exception:
                pass

            remediation = rule["remediation_fn"](match, command, stderr, None) + playbook_hint
            return {
                "failure_intent": rule["intent"],
                "regex_pattern": rule["regex"],
                "remediation": remediation,
                "engine": "heuristic"
            }
    return None

def distill_failure_via_ollama(command: str, stderr: str, cursor) -> dict | None:
    """Pipes novel or complex failures through local Qwen2.5 to extract the structural taboo rule."""
    try:
        cursor.execute("SELECT action_name, target_script_path FROM procedures LIMIT 20")
        procedures = cursor.fetchall()
        graph_context = "\nAvailable Playbooks in Graph:\n"
        for p in procedures:
            graph_context += f"- Action: {p[0]} -> Script: {p[1]}\n"
    except sqlite3.OperationalError:
        graph_context = "\n(No playbooks available in graph)\n"
        
    user_prompt = f"Command Attempted: `{command}`\nError Output: `{stderr}`\n{graph_context}\nAnalyze and distill this failure."
    
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": user_prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "format": "json",
        "keep_alive": 0,
        "options": {"temperature": 0.1, "num_predict": 256}
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL, 
        data=payload, 
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            response_text = body.get("response", "{}")
            res = json.loads(response_text)
            res["engine"] = "ollama_qwen"
            return res
    except Exception as e:
        print(f"[!] [Ollama Distillation Skipped/Failed]: {e}")
        return None

def mine_the_graveyard():
    """Scans ULM for failed tool executions and seeds the taboo interceptor using the hybrid engine."""
    if not ULM_DB_PATH.exists():
        print(f"[-] Error: ULM Database not found at {ULM_DB_PATH}")
        return

    print(f"[*] Connecting to ULM memory core at: {ULM_DB_PATH}")
    conn = sqlite3.connect(ULM_DB_PATH, isolation_level=None)
    conn.execute('pragma journal_mode=wal')
    cursor = conn.cursor()

    setup_taboo_matrix(cursor)

    # Watermark tracking cursor to prevent re-mining identical rows
    last_mined_id = 0
    try:
        cursor.execute("SELECT pref_value FROM preferences WHERE pref_key = 'last_mined_tool_log_id'")
        pref_row = cursor.fetchone()
        if pref_row and pref_row[0] and pref_row[0].isdigit():
            last_mined_id = int(pref_row[0])
    except Exception:
        pass

    try:
        cursor.execute("""
            SELECT id, command, stderr 
            FROM tool_execution_logs 
            WHERE id > ? AND exit_code != 0 AND exit_code IS NOT NULL
            ORDER BY id ASC
            LIMIT 50
        """, (last_mined_id,))
        failed_executions = cursor.fetchall()
    except sqlite3.OperationalError:
        print("[-] 'tool_execution_logs' table empty or not found.")
        failed_executions = []

    if not failed_executions:
        print(f"[*] Graveyard is clean (watermark cursor: {last_mined_id}). No unmined failures detected.")
        conn.close()
        return

    print(f"[*] Found {len(failed_executions)} unmined execution failures (watermark: >{last_mined_id}). Running Tier-2 Hybrid Distillation...")

    success_count = 0
    heuristic_count = 0
    ollama_count = 0
    max_mined_id = last_mined_id

    for log_id, cmd, err in failed_executions:
        if log_id > max_mined_id:
            max_mined_id = log_id

        # 1. Try Instant Heuristic Classifier (0ms, 0 VRAM)
        rule = match_deterministic_heuristic(cmd, err, cursor)
        
        # 2. Fall back to local Ollama if novel/unrecognized
        if not rule:
            print(f"   [Novel Failure] Routing to Ollama: `{cmd[:40]}...`")
            rule = distill_failure_via_ollama(cmd, err, cursor)

        if rule and "failure_intent" in rule:
            intent = str(rule.get("failure_intent", "")).strip()[:80]
            regex = str(rule.get("regex_pattern", "")).strip()[:200]
            remediation = str(rule.get("remediation", "")).strip()[:300]
            engine_used = rule.get("engine", "unknown")
            
            # Validate regex syntax safety
            if regex:
                try:
                    re.compile(regex)
                except re.error:
                    regex = ""

            try:
                if engine_used == "heuristic":
                    # Verified deterministic heuristics write safely to active rules
                    cursor.execute("""
                        INSERT INTO taboo_rules (failure_intent, regex_pattern, remediation, last_seen)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(failure_intent) DO UPDATE SET 
                            hit_count = hit_count + 1,
                            remediation = excluded.remediation,
                            last_seen = CURRENT_TIMESTAMP
                    """, (intent, regex, remediation))
                    print(f"   [+] [HEURISTIC] Active Rule: [{intent}] -> {remediation[:60]}...")
                    heuristic_count += 1
                    success_count += 1
                else:
                    # Novel LLM-generated rules are sanitized and quarantined in pending_taboo_rules
                    # Strip shell metacharacters and command substitutions from unverified remediations
                    safe_remediation = re.sub(r'[\$`;&|]', '', remediation)
                    cursor.execute("""
                        INSERT INTO pending_taboo_rules (failure_intent, regex_pattern, remediation, hit_count, status, created_at)
                        VALUES (?, ?, ?, 1, 'pending', CURRENT_TIMESTAMP)
                        ON CONFLICT(failure_intent) DO UPDATE SET 
                            hit_count = hit_count + 1
                    """, (intent, regex, safe_remediation))
                    print(f"   [+] [QUARANTINE] Stored novel LLM rule in pending_taboo_rules: [{intent}]")
                    ollama_count += 1
                    success_count += 1
            except Exception as db_err:
                print(f"   [-] DB Insert Error: {db_err}")

    # Advance watermark cursor in preferences
    try:
        cursor.execute("""
            INSERT INTO preferences (pref_key, pref_value, updated_at)
            VALUES ('last_mined_tool_log_id', ?, datetime('now'))
            ON CONFLICT(pref_key) DO UPDATE SET pref_value = excluded.pref_value, updated_at = excluded.updated_at
        """, (str(max_mined_id),))
    except Exception as pref_err:
        print(f"[-] Error updating watermark cursor: {pref_err}")

    # Auto-retire dead failure patterns not observed in 30 days
    retire_stale_taboos(cursor, max_age_days=30)

    print(f"\n[+] Mining Complete. Seeded/Updated {success_count} rules (⚡ {heuristic_count} instant heuristics, 🧠 {ollama_count} LLM distillations).")
    conn.close()

# Alias for daemon integration
distill_graveyard = mine_the_graveyard

if __name__ == "__main__":
    mine_the_graveyard()