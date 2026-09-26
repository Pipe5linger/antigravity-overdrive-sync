#!/usr/bin/env python3
"""
ULM Swarm Orchestrator
======================
Orchestrates specialized subagent role playbooks:
  1. Security Auditor (sec_auditor.py)
  2. Test Harness Engineer (test_engineer.py)
  3. Migration Architect (migration_architect.py)

Supports sequential or parallel execution ([PARALLEL SWARM]),
and writes execution telemetry back into ULM's SQLite procedures matrix.
"""

import os
import sys
import time
import argparse
import datetime
import sqlite3
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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

ROLES = {
    "security": {
        "node_id": "pb_sec_auditor",
        "name": "Security Auditor",
        "script": PROJECT_ROOT / "scripts" / "playbooks" / "sec_auditor.py",
        "icon": "🔒"
    },
    "test": {
        "node_id": "pb_test_engineer",
        "name": "Test Harness Engineer",
        "script": PROJECT_ROOT / "scripts" / "playbooks" / "test_engineer.py",
        "icon": "🛠️ "
    },
    "architect": {
        "node_id": "pb_migration_architect",
        "name": "Migration & Systems Architect",
        "script": PROJECT_ROOT / "scripts" / "playbooks" / "migration_architect.py",
        "icon": "📐"
    }
}

def record_procedure_status(node_id, status_str):
    if not DB_PATH.exists():
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        cursor = conn.cursor()
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
            UPDATE procedures
            SET last_execution_status = ?, updated_at = ?
            WHERE node_id = ?;
        """, (status_str, now_str, node_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Warning: Failed to record procedure status for {node_id}: {e}")

def execute_role(role_key):
    role = ROLES[role_key]
    script = role["script"]
    name = role["name"]
    node_id = role["node_id"]
    icon = role["icon"]

    print(f"\n{icon} [SWARM AGENT: {name}] Launching task...")
    t0 = time.perf_counter()
    
    res = subprocess.run(
        [sys.executable, str(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    duration = time.perf_counter() - t0
    success = (res.returncode == 0)
    status_str = f"SUCCESS ({duration:.2f}s)" if success else f"FAILED (Exit {res.returncode})"

    record_procedure_status(node_id, "VERIFIED" if success else f"FAIL_{res.returncode}")

    return {
        "key": role_key,
        "name": name,
        "success": success,
        "duration": duration,
        "stdout": res.stdout,
        "stderr": res.stderr
    }

def run_swarm(roles_to_run, parallel=False):
    mode_str = "PARALLEL SWARM" if parallel else "SEQUENTIAL DISPATCH"
    print(f"\n🚀 [ULM SWARM ORCHESTRATOR] Mode: [{mode_str}]")
    print(f"   Target Roles: {', '.join([ROLES[r]['name'] for r in roles_to_run])}")
    print("=" * 75)

    results = []
    t_start = time.perf_counter()

    if parallel and len(roles_to_run) > 1:
        with ThreadPoolExecutor(max_workers=len(roles_to_run)) as executor:
            future_to_role = {executor.submit(execute_role, r): r for r in roles_to_run}
            for future in as_completed(future_to_role):
                results.append(future.result())
    else:
        for r in roles_to_run:
            results.append(execute_role(r))

    total_time = time.perf_counter() - t_start
    print("\n" + "=" * 75)
    print("🏁 [SWARM ORCHESTRATOR SUMMARY]")
    all_ok = True
    for res in sorted(results, key=lambda x: x["name"]):
        mark = "✓ PASSED" if res["success"] else "✗ FAILED"
        print(f"  {res['name']:<32} : {mark} ({res['duration']:.2f}s)")
        if not res["success"]:
            all_ok = False
            if res["stderr"]:
                print(f"    [ERR] {res['stderr'].strip()[:160]}")
    
    print("-" * 75)
    print(f"  Total Swarm Execution Time : {total_time:.2f}s")
    swarm_status = "ALL_SYSTEMS_OPERATIONAL" if all_ok else "SWARM_DEGRADED"
    print(f"  Overall Swarm Health       : {swarm_status}")
    print("=" * 75)

    record_procedure_status("pb_swarm_audit", "VERIFIED" if all_ok else "DEGRADED")
    return all_ok

def main():
    parser = argparse.ArgumentParser(description="ULM Subagent Swarm Orchestrator")
    parser.add_argument("--all", action="store_true", help="Run all subagent roles")
    parser.add_argument("--sec", action="store_true", help="Run Security Auditor")
    parser.add_argument("--test", action="store_true", help="Run Test Harness Engineer")
    parser.add_argument("--arch", action="store_true", help="Run Migration & Systems Architect")
    parser.add_argument("--parallel", action="store_true", help="Run in parallel swarm mode")

    args = parser.parse_args()

    selected = []
    if args.sec:
        selected.append("security")
    if args.test:
        selected.append("test")
    if args.arch:
        selected.append("architect")
    
    if args.all or not selected:
        selected = ["security", "test", "architect"]

    success = run_swarm(selected, parallel=args.parallel)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
