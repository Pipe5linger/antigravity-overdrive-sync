#!/usr/bin/env python3
"""
ULM Test Harness Engineer Role Playbook
=======================================
Executes the automated pytest suite, runs concurrency lock-verification,
and benchmarks context prompt token injection limits against the bounded budget.
"""

import os
import sys
import time
import sqlite3
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

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

def run_pytest_suite():
    print("[*] Running automated unit and integration tests (pytest)...")
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    passed = (res.returncode == 0)
    summary_line = ""
    for line in res.stdout.splitlines():
        if "passed" in line or "failed" in line or "error" in line:
            summary_line = line.strip()
    
    if passed:
        print(f"  ✓ Pytest Suite: PASSED ({summary_line})")
    else:
        print(f"  [-] Pytest Suite: FAILED")
        for line in res.stdout.splitlines()[-10:]:
            print(f"    {line}")
    return passed

def run_concurrency_bench(threads=10, queries_per_thread=20):
    print(f"[*] Running concurrency lock-verification ({threads} threads, {queries_per_thread} ops/thread)...")
    if not DB_PATH.exists():
        print("  [-] Database does not exist yet; skipping concurrency benchmark.")
        return True

    errors = []
    latencies = []

    def worker(worker_id):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            cursor = conn.cursor()
            
            for q in range(queries_per_thread):
                t0 = time.perf_counter()
                cursor.execute("SELECT COUNT(*) FROM facts;")
                cursor.fetchone()
                # Fast read on procedures
                cursor.execute("SELECT node_id, last_execution_status FROM procedures LIMIT 5;")
                cursor.fetchall()
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000)
            conn.close()
        except Exception as e:
            errors.append(f"Worker {worker_id} error: {e}")

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(worker, i) for i in range(threads)]
        for f in futures:
            f.result()
    total_time = time.perf_counter() - t_start

    if errors:
        print(f"  [-] Concurrency benchmark FAILED with {len(errors)} error(s):")
        for err in errors[:5]:
            print(f"    {err}")
        return False

    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    p99_lat = sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0
    tps = (threads * queries_per_thread) / total_time if total_time > 0 else 0

    print(f"  ✓ Concurrency Lock Check: PASSED (Zero lockouts)")
    print(f"    Throughput: {tps:.1f} queries/sec | Avg: {avg_lat:.2f}ms | p99: {p99_lat:.2f}ms")
    return True

def run_prompt_budget_check():
    print("[*] Validating Prompt Injection Context Budget (< 2,000 tokens ceiling)...")
    try:
        from core.assembler import DynamicPromptAssembler

        assembler = DynamicPromptAssembler()
        block = assembler.assemble_compact_prompt()
        approx_tokens = len(block) // 4
        ceiling = 2000

        print(f"  ✓ Assembled Compact Prompt: ~{approx_tokens} tokens (Budget ceiling: {ceiling})")
        if approx_tokens > ceiling:
            print(f"  [-] WARNING: Injected prompt exceeded token ceiling! ({approx_tokens} > {ceiling})")
            return False
        print(f"  ✓ Budget Adherence: VERIFIED ({approx_tokens}/{ceiling} tokens used)")
        return True
    except Exception as e:
        print(f"  [-] Prompt budget check warning/error: {e}")
        return False

def run_test_engineer():
    print("🛠️  [ULM Test Harness Engineer] Initiating automated test & validation suite...")
    print("=" * 70)
    
    p1 = run_pytest_suite()
    p2 = run_concurrency_bench()
    p3 = run_prompt_budget_check()
    
    print("=" * 70)
    all_passed = p1 and p2 and p3
    if all_passed:
        print("  ✓ ALL TEST HARNESS CHECKS PASSED.")
    else:
        print("  [-] TEST HARNESS REPORTED FAILURES.")
    print("=" * 70)
    return all_passed

if __name__ == "__main__":
    success = run_test_engineer()
    sys.exit(0 if success else 1)
