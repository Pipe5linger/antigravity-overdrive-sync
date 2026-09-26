#!/usr/bin/env python3
"""
Playbook: inspect_db.py
Inspects SQLite table statistics, row counts, schema columns, or sample rows
without requiring ad-hoc inline Python scripts.

Usage:
    python scripts/playbooks/inspect_db.py [--table TABLE_NAME] [--limit 5] [--schema]
"""

import sys
import argparse
import sqlite3
from pathlib import Path

# Enforce UTF-8 on Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# Workspace Setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"

def inspect(table=None, limit=5, show_schema=False):
    if not DB_PATH.exists():
        print(f"[-] Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    cursor = conn.cursor()

    if not table:
        print("=== 📊 ULM Database Table Statistics ===")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
        for t in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM \"{t}\"")
                count = cursor.fetchone()[0]
                print(f"  • {t:<24} : {count:,} rows")
            except Exception as e:
                print(f"  • {t:<24} : Error ({e})")
        conn.close()
        return

    # Specific table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    valid_tables = {row[0] for row in cursor.fetchall()}
    if table not in valid_tables:
        print(f"[-] Error: Table '{table}' not found in database.")
        conn.close()
        return

    print(f"=== Table: {table} ===")
    if show_schema:
        print("\n--- Columns ---")
        cursor.execute(f"PRAGMA table_info(\"{table}\")")
        for col in cursor.fetchall():
            pk = " [PK]" if col[5] else ""
            print(f"  - {col[1]} ({col[2]}){pk}")

    print(f"\n--- Sample Data (Limit {limit}) ---")
    cursor.execute(f"SELECT * FROM \"{table}\" LIMIT ?", (limit,))
    rows = cursor.fetchall()
    cursor.execute(f"PRAGMA table_info(\"{table}\")")
    col_names = [c[1] for c in cursor.fetchall()]

    if not rows:
        print("  (Table is empty)")
    else:
        for i, row in enumerate(rows, 1):
            print(f"\n[Row {i}]")
            for col_name, val in zip(col_names, row):
                val_str = str(val)
                if len(val_str) > 100:
                    val_str = val_str[:97] + "..."
                print(f"  {col_name:<16}: {val_str}")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect ULM SQLite tables and schemas")
    parser.add_argument("--table", "-t", type=str, help="Specific table to inspect")
    parser.add_argument("--limit", "-n", type=int, default=5, help="Number of sample rows (default: 5)")
    parser.add_argument("--schema", "-s", action="store_true", help="Display column names and data types")
    args = parser.parse_args()

    inspect(table=args.table, limit=args.limit, show_schema=args.schema)
