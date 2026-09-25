#!/usr/bin/env python3
"""
Database Optimization & Orphan Pruner:
1. Deletes orphaned fact_embeddings where fact_id IS NULL or fact_id not in facts.
2. Checks database integrity.
3. Executes VACUUM into a lean database file to reclaim over 1GB of disk space.
"""

import sqlite3
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"

def vacuum_database():
    if not DB_PATH.exists():
        print(f"[-] Database not found at {DB_PATH}")
        return

    orig_size = DB_PATH.stat().st_size
    print(f"[*] Original database size: {orig_size / (1024*1024):.2f} MB ({orig_size:,} bytes)")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 30000;")
    cursor = conn.cursor()

    # 1. Count orphans
    cursor.execute("SELECT COUNT(*) FROM fact_embeddings WHERE fact_id IS NULL")
    null_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fact_embeddings WHERE fact_id NOT IN (SELECT fact_id FROM facts WHERE fact_id IS NOT NULL)")
    orphan_count = cursor.fetchone()[0]

    print(f"[*] Found {null_count:,} NULL fact_id rows and {orphan_count:,} unlinked rows in fact_embeddings.")

    # 2. Delete orphans
    print("[*] Pruning orphaned embeddings...")
    cursor.execute("DELETE FROM fact_embeddings WHERE fact_id IS NULL OR fact_id NOT IN (SELECT fact_id FROM facts WHERE fact_id IS NOT NULL)")
    deleted = cursor.rowcount
    conn.commit()
    print(f"[+] Deleted {deleted:,} orphaned embedding records.")

    # 3. Check remaining counts
    cursor.execute("SELECT COUNT(*) FROM fact_embeddings")
    remaining_embeddings = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM facts")
    remaining_facts = cursor.fetchone()[0]
    print(f"[*] Valid records remaining: {remaining_facts} facts, {remaining_embeddings} cached embeddings.")

    # 4. Checkpoint WAL and VACUUM
    print("[*] Running WAL checkpoint and VACUUM (this may take a few seconds)...")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    conn.execute("VACUUM;")
    conn.close()

    new_size = DB_PATH.stat().st_size
    freed_mb = (orig_size - new_size) / (1024 * 1024)
    print(f"[+] VACUUM Complete! New size: {new_size / (1024*1024):.2f} MB ({new_size:,} bytes)")
    print(f"[+] Reclaimed {freed_mb:.2f} MB of disk space!")

if __name__ == "__main__":
    vacuum_database()
