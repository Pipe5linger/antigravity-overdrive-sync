#!/usr/bin/env python3
"""
Playbook: ingest_sessions.py
Triggers immediate transcript ingestion across Antigravity and Cline workspaces,
extracting verified facts and developer profile traits into SQLite.

Usage:
    python scripts/playbooks/ingest_sessions.py [--force]
"""

import sys
import argparse
from pathlib import Path

# Workspace Setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.database import ULMDatabase, DEFAULT_DB_PATH
from core.consolidator import MemoryConsolidator

def run_ingest(force=False):
    print("=== 📥 ULM Transcript & Session Ingestion ===")
    db = ULMDatabase(DEFAULT_DB_PATH)
    mc = MemoryConsolidator(db)
    result = mc.ingest_transcripts(force_all=force)
    print(f"[+] Ingestion Summary: {result.get('sessions', 0)} sessions parsed, {result.get('facts_extracted', 0)} new facts recorded.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger immediate transcript ingestion into ULM")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-ingestion of all session logs")
    args = parser.parse_args()

    run_ingest(force=args.force)
