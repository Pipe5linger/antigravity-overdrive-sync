#!/usr/bin/env python3
"""
Populates the taboo_rules table in sync_state.db with an extensive suite of
pre-emptive landmines across Windows, PowerShell, Python, Git, and SQLite.
"""

import sqlite3
import sys
from pathlib import Path

# Workspace Setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"

TABOO_LANDMINES = [
    # 1. PowerShell Env Variable & Execution Traps
    {
        "failure_intent": "PowerShell Env Assignment Inline Execution",
        "regex_pattern": r"\$env:\w+\s*=\s*['\"].*?['\"]\s*;\s*python",
        "remediation": "PowerShell inline assignment with semicolons often fails depending on invocation context. Use cmd.exe /c \"set VAR=val && python ...\" or configure the environment in Python before execution."
    },
    {
        "failure_intent": "PowerShell Nested Quote Stripping",
        "regex_pattern": r"python\s+-c\s+[\"'].*?[\"'].*?[\"']",
        "remediation": "PowerShell strips inner quotes in python -c commands. Write python scripts or test commands into a temporary .py file and execute it directly."
    },
    {
        "failure_intent": "PowerShell Raw Curl Collision",
        "regex_pattern": r"^curl\s+-X\s+",
        "remediation": "In Windows PowerShell 5.1, 'curl' is an alias for Invoke-WebRequest with incompatible arguments. Use curl.exe or Python urllib/requests."
    },

    # 2. Windows Filesystem & Encoding Landmines
    {
        "failure_intent": "Windows Backslash Regex Escape Trap",
        "regex_pattern": r"re\.(?:search|match|findall|sub)\([\"'][^\"']*\\[a-zA-Z]",
        "remediation": "Windows path backslashes in regex or standard string literals trigger invalid escape sequence warnings. Use raw strings r\"...\" and forward slashes for filesystem paths."
    },
    {
        "failure_intent": "Windows Subprocess Default Encoding Trap",
        "regex_pattern": r"subprocess\.(?:run|Popen|check_output)\(.*?(?!encoding=)",
        "remediation": "Subprocess outputs on Windows default to OEM codepage (cp437/cp1252), causing UnicodeDecodeError on UTF-8 emoji or symbols. Always specify encoding='utf-8', errors='replace'."
    },
    {
        "failure_intent": "Git CRLF Script Mutilation",
        "regex_pattern": r"/bin/bash:.*?\r: bad interpreter",
        "remediation": "Windows CRLF line endings break Linux/WSL/bash shell scripts. Set .gitattributes text eol=lf or convert using tr -d '\\r'."
    },

    # 3. SQLite Concurrency & Locking Landmines
    {
        "failure_intent": "SQLite Database Is Locked Concurrency Crash",
        "regex_pattern": r"sqlite3\.OperationalError: database is locked",
        "remediation": "Multiple processes or unclosed cursors are contending for the DB. Always execute 'PRAGMA busy_timeout = 5000;' and 'PRAGMA journal_mode = WAL;' immediately upon connection, and use context managers."
    },
    {
        "failure_intent": "SQLite Unindexed FTS5 Query Overhead",
        "regex_pattern": r"SELECT\s+.*?\s+FROM\s+facts\s+WHERE\s+fact\s+LIKE\s+['\"]%",
        "remediation": "Leading wildcard LIKE '%query%' scans the entire table and bypasses indices. Use the FTS5 virtual table 'facts_fts MATCH ?' for sub-millisecond full-text queries."
    },

    # 4. Local Model & ComfyUI Runtime Traps
    {
        "failure_intent": "ComfyUI Local API Null Value Serialization",
        "regex_pattern": r"KeyError: ['\"]inputs['\"]",
        "remediation": "ComfyUI prompt graph nodes crash if optional inputs are passed as null/None instead of omitting the key entirely from the JSON payload."
    },
    {
        "failure_intent": "PyTorch Cuda Out Of Memory Diffusion Spike",
        "regex_pattern": r"torch\.cuda\.OutOfMemoryError",
        "remediation": "RTX 4070 12GB VRAM allocation ceiling breached. Run gc.collect() and torch.cuda.empty_cache(), or execute python scripts/generators_and_tools/vram_guard.py."
    },
    {
        "failure_intent": "Ollama Local Service Unreachable",
        "regex_pattern": r"urllib\.error\.URLError:.*?(?:Connection refused|10061)",
        "remediation": "Local Ollama service (127.0.0.1:11434) is stopped or restarting. Verify process status or fall back to rule-based deterministic heuristics."
    },

    # 5. Master Protocol Sovereign Target Violation
    {
        "failure_intent": "Duplicate GEMINI.md Rule Poisoning",
        "regex_pattern": r"(?:write_to_file|replace_file_content).*?(?:D:\\AI\\GEMINI\.md|Projects\\.*?GEMINI\.md|AGENTS\.md)",
        "remediation": "CRITICAL SOVEREIGN RULE: Never write GEMINI.md or AGENTS.md in workspace subdirectories. The ONLY allowed target is C:\\Users\\boben\\.gemini\\GEMINI.md."
    }
]

def populate_taboos():
    print(f"[*] Connecting to ULM Database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    cursor = conn.cursor()

    inserted = 0
    updated = 0

    for rule in TABOO_LANDMINES:
        cursor.execute("SELECT id, remediation FROM taboo_rules WHERE failure_intent = ?", (rule["failure_intent"],))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE taboo_rules 
                SET regex_pattern = ?, remediation = ?, hit_count = hit_count + 1
                WHERE id = ?
            """, (rule["regex_pattern"], rule["remediation"], existing[0]))
            updated += 1
        else:
            cursor.execute("""
                INSERT INTO taboo_rules (failure_intent, regex_pattern, remediation, hit_count)
                VALUES (?, ?, ?, 1)
            """, (rule["failure_intent"], rule["regex_pattern"], rule["remediation"]))
            inserted += 1

    conn.commit()
    conn.close()
    print(f"[+] Taboo Population Complete: {inserted} added, {updated} refreshed.")

if __name__ == "__main__":
    populate_taboos()
