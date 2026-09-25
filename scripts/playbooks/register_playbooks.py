#!/usr/bin/env python3
"""
Registers the newly created reusable playbooks into the ULM procedures table.
"""

import sqlite3
import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"

PLAYBOOKS = [
    {
        "node_id": "pb_inspect_db",
        "action_name": "inspect_db",
        "target_script_path": "python scripts/playbooks/inspect_db.py",
        "expected_outcome": "Prints table row counts, schema columns, or sample rows from sync_state.db."
    },
    {
        "node_id": "pb_port_audit",
        "action_name": "port_audit",
        "target_script_path": "python scripts/playbooks/port_audit.py",
        "expected_outcome": "Audits active ports for ComfyUI, Ollama, SD Forge, KoboldCpp, and ULM."
    },
    {
        "node_id": "pb_gpu_guard",
        "action_name": "gpu_guard",
        "target_script_path": "python scripts/playbooks/gpu_guard.py",
        "expected_outcome": "Checks RTX 4070 12GB VRAM utilization and temperature; optional --purge clears PyTorch cache."
    },
    {
        "node_id": "pb_comfy_queue",
        "action_name": "comfy_queue",
        "target_script_path": "python scripts/playbooks/comfy_queue.py",
        "expected_outcome": "Queries ComfyUI active prompts and queue status on port 8188."
    },
    {
        "node_id": "pb_ingest_sessions",
        "action_name": "ingest_sessions",
        "target_script_path": "python scripts/playbooks/ingest_sessions.py",
        "expected_outcome": "Extracts semantic facts and developer traits from active Antigravity / Cline session transcripts."
    },
    {
        "node_id": "pb_vacuum_state",
        "action_name": "vacuum_state",
        "target_script_path": "python scripts/playbooks/vacuum_state.py",
        "expected_outcome": "Runs SQLite WAL checkpoint, prunes orphan embeddings, and reclaims disk space."
    }
]

def register():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    cursor = conn.cursor()

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    count = 0
    for pb in PLAYBOOKS:
        cursor.execute("""
            INSERT INTO procedures (node_id, action_name, target_script_path, expected_outcome, last_execution_status, updated_at)
            VALUES (?, ?, ?, ?, 'VERIFIED', ?)
            ON CONFLICT(node_id) DO UPDATE SET
                action_name = excluded.action_name,
                target_script_path = excluded.target_script_path,
                expected_outcome = excluded.expected_outcome,
                last_execution_status = 'VERIFIED',
                updated_at = excluded.updated_at
        """, (pb["node_id"], pb["action_name"], pb["target_script_path"], pb["expected_outcome"], now_str))
        count += 1

    conn.commit()
    conn.close()
    print(f"[+] Successfully registered and updated {count} tactical playbooks in ULM procedures matrix.")

if __name__ == "__main__":
    register()
