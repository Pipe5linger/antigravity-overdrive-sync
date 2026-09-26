#!/usr/bin/env python3
"""
ULM Database Quick Inspector
----------------------------
Instant diagnostic summary of the local SQLite WAL memory ledger.
"""

import sqlite3
import os
import sys

DB_PATH = "db/sync_state.db"

def inspect_db(db_path: str = DB_PATH):
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Pragmas
    journal_mode = cur.execute("PRAGMA journal_mode;").fetchone()[0]
    integrity = cur.execute("PRAGMA integrity_check;").fetchone()[0]

    # Tables
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()]

    print("=" * 65)
    print(f" ULM Ledger Health: {db_path} ({os.path.getsize(db_path) / (1024*1024):.2f} MB)")
    print("=" * 65)
    print(f"  Journal Mode : {journal_mode.upper()} (WAL expected)")
    print(f"  Integrity    : {integrity.upper()}")
    print("-" * 65)
    print("  Table Record Counts:")
    for t in tables:
        try:
            cnt = cur.execute(f"SELECT COUNT(*) FROM \"{t}\";").fetchone()[0]
            print(f"    - {t:<28}: {cnt:>8} rows")
        except Exception as e:
            print(f"    - {t:<28}: [ERROR {e}]")
    print("-" * 65)

    # If taboos or rules exist, print recent
    for candidate in ["taboos", "taboo_rules", "negative_constraints"]:
        if candidate in tables:
            print(f"  Sample from '{candidate}':")
            for row in cur.execute(f"SELECT * FROM \"{candidate}\" LIMIT 5;").fetchall():
                print(f"    {row}")
            break

    print("=" * 65)
    conn.close()

if __name__ == "__main__":
    inspect_db()
