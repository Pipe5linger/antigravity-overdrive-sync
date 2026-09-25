#!/usr/bin/env python3
"""
Playbook: vacuum_state.py
Executes SQLite WAL checkpoint, prunes any unlinked embedding records,
and reclaims unused disk space via VACUUM.

Usage:
    python scripts/playbooks/vacuum_state.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generators_and_tools.vacuum_database import vacuum_database

if __name__ == "__main__":
    print("=== 🧹 ULM Database Vacuum & Defragmentation ===")
    vacuum_database()
