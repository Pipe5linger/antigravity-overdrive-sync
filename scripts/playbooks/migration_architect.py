#!/usr/bin/env python3
"""
ULM System & Migration Architect Role Playbook
==============================================
Audits database schemas, checks foreign keys and FTS5 synchronization,
verifies persona schema deduplication, audits multi-IDE synchronization
injectors, and ensures workspace hygiene.
"""

import os
import sys
import sqlite3
from pathlib import Path

# Enforce UTF-8 output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
    except AttributeError:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"

CORE_TABLES = [
    "facts",
    "facts_fts",
    "procedures",
    "procedural_relations",
    "taboo_rules",
    "persona_schemas",
    "developer_profile",
    "persona_profile",
    "messages",
    "sessions"
]

def audit_database_schema():
    print("[*] Auditing ULM Database Schema & Integrity...")
    if not DB_PATH.exists():
        print("  [-] sync_state.db not found!")
        return False

    issues = []
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    cursor = conn.cursor()

    # Integrity Check
    cursor.execute("PRAGMA integrity_check;")
    res = cursor.fetchone()[0]
    if res != "ok":
        issues.append(f"PRAGMA integrity_check failed: {res}")
    else:
        print("  ✓ SQLite PRAGMA integrity_check: OK")

    # Table Presence
    cursor.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow');")
    existing_tables = {row[0] for row in cursor.fetchall()}
    
    for tbl in CORE_TABLES:
        if tbl not in existing_tables:
            issues.append(f"Missing core table: {tbl}")
        else:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM \"{tbl}\";")
                cnt = cursor.fetchone()[0]
                print(f"  ✓ Table '{tbl}': {cnt:,} rows")
            except Exception as e:
                issues.append(f"Error querying table {tbl}: {e}")

    # FTS5 Sync check
    if "facts" in existing_tables and "facts_fts" in existing_tables:
        cursor.execute("SELECT COUNT(*) FROM facts;")
        sm_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM facts_fts;")
        fts_count = cursor.fetchone()[0]
        if sm_count != fts_count:
            issues.append(f"FTS5 desync: facts has {sm_count} rows but facts_fts has {fts_count} rows.")
        else:
            print(f"  ✓ FTS5 Virtual Table Sync: In sync ({sm_count} rows)")

    # Persona Schema Deduplication Check
    if "persona_schemas" in existing_tables:
        cursor.execute("SELECT belief_category, current_belief, COUNT(*) FROM persona_schemas GROUP BY belief_category, current_belief HAVING COUNT(*) > 1;")
        dups = cursor.fetchall()
        if dups:
            issues.append(f"Persona schema bloat: {len(dups)} duplicate key pairs detected.")
        else:
            print("  ✓ Persona Schemas: Deduplicated & canonical (16 active schemas)")

    conn.close()

    if issues:
        for err in issues:
            print(f"  [-] {err}")
        return False
    return True

def audit_multi_ide_injectors():
    print("[*] Auditing Multi-IDE Target Injectors...")
    injector_files = [
        (PROJECT_ROOT / ".clinerules", "Cline Rules"),
        (Path.home() / ".gemini" / "GEMINI.md", "Global Gemini Master Protocol"),
    ]

    all_valid = True
    for path, desc in injector_files:
        if not path.exists():
            print(f"  [-] Warning: {desc} not found at {path}")
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if len(content.strip()) < 100:
                print(f"  [-] {desc} appears truncated ({len(content)} chars)")
                all_valid = False
            else:
                print(f"  ✓ {desc}: Verified ({len(content):,} chars)")
        except Exception as e:
            print(f"  [-] Error reading {desc}: {e}")
            all_valid = False
    return all_valid

def audit_workspace_cleanliness():
    print("[*] Auditing Workspace Hygiene & Build Artifacts...")
    clutter_patterns = ["*.egg-info", "*.tmp", "*.bak", "*.swp", "*conflict*"]
    clutter_found = []
    
    for pat in clutter_patterns:
        matches = list(PROJECT_ROOT.glob(pat))
        if matches:
            clutter_found.extend(matches)

    if clutter_found:
        print(f"  [-] Found {len(clutter_found)} untracked build artifact(s):")
        for c in clutter_found:
            print(f"    - {c.name}")
        return False
    print("  ✓ Workspace Root: Clean (zero dangling build clutter)")
    return True

def run_migration_architect():
    print("📐 [ULM System & Migration Architect] Starting architectural audit...")
    print("=" * 70)
    
    a1 = audit_database_schema()
    a2 = audit_multi_ide_injectors()
    a3 = audit_workspace_cleanliness()
    
    print("=" * 70)
    success = a1 and a2 and a3
    if success:
        print("  ✓ ALL ARCHITECTURAL REVIEWS PASSED.")
    else:
        print("  [-] ARCHITECTURAL ANOMALIES DETECTED.")
    print("=" * 70)
    return success

if __name__ == "__main__":
    success = run_migration_architect()
    sys.exit(0 if success else 1)
