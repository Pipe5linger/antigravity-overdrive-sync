#!/usr/bin/env python3
"""
File    : stress_test_extreme.py
Purpose : Adversarial, Multi-Vector Concurrency & Scaling Stress Test for ULM
          Pushes ULM to the physical breaking point across:
          1. Concurrent Thread Hammer (10 -> 25 -> 50 Threads slamming SQLite WAL)
          2. TOCTOU File Injector Collision (20 Threads slamming atomic_write with backoff)
          3. Vector Math & Pairwise Cosine Matrix Scaling Cliff (N=250 to 5,000)
          4. Taboo Graveyard Flood & Auto-Retirement Engine Under Load
          5. High-Frequency Persona Deduplication Engine Stress
"""

import os
import sys
import time
import shutil
import random
import string
import sqlite3
import datetime
import threading
import concurrent.futures
from pathlib import Path
import numpy as np

# Workstation Path Setup
BENCHMARK_DIR = Path(__file__).resolve().parent
REPO_ROOT = BENCHMARK_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from core.database import ULMDatabase
from core.utils import atomic_write
from scripts.generators_and_tools.taboo_extractor import (
    setup_taboo_matrix,
    match_deterministic_heuristic,
    retire_stale_taboos,
    DETERMINISTIC_RULES
)

STRESS_DB_PATH = BENCHMARK_DIR / "stress_test_extreme.db"
STRESS_SCRATCH_DIR = BENCHMARK_DIR / "scratch_stress"


def print_banner(title: str):
    width = 75
    print("\n" + "=" * width)
    print(f"🔥 {title.upper().center(width - 4)} 🔥")
    print("=" * width)


def cleanup_stress_artifacts():
    """Wipes ephemeral stress testing artifacts."""
    for p in [STRESS_DB_PATH, STRESS_DB_PATH.with_suffix(".db-wal"), STRESS_DB_PATH.with_suffix(".db-shm")]:
        if p.exists():
            try:
                os.remove(p)
            except Exception:
                pass
    if STRESS_SCRATCH_DIR.exists():
        try:
            shutil.rmtree(STRESS_SCRATCH_DIR)
        except Exception:
            pass


# ============================================================================
# STAGE 1: CONCURRENT THREAD HAMMER (10 -> 25 -> 50 Threads)
# ============================================================================
def stage_1_concurrency_hammer(db: ULMDatabase, num_threads: int, ops_per_thread: int):
    print(f"\n[*] [STAGE 1] Launching {num_threads} Concurrent Worker Threads ({ops_per_thread} ops/thread = {num_threads * ops_per_thread} total ops)...")
    
    errors = []
    latencies = []
    busy_errors = []
    start_time = time.perf_counter()

    def worker_task(thread_id: int):
        thread_latencies = []
        for i in range(ops_per_thread):
            t0 = time.perf_counter()
            op_type = i % 4
            try:
                if op_type == 0:
                    # Write: Upsert Fact
                    fact_id = f"fact_{thread_id}_{i}"
                    fact_text = f"Synthetic stress fact {i} from thread {thread_id} exploring quantum graph theory."
                    db.upsert_fact(fact=fact_text, category="stress_test", confidence=0.95, project_tag="benchmark")
                elif op_type == 1:
                    # Write: Upsert Session + Insert Message
                    sess_id = f"sess_{thread_id}_{i % 10}"
                    db.upsert_session(sess_id, "stress_worker", "ConcurrencyStress")
                    db.insert_message(sess_id, "user" if i % 2 == 0 else "model", f"Payload {i} from worker {thread_id}", datetime.datetime.now().isoformat())
                elif op_type == 2:
                    # Read / FTS5 Search: Query Facts
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT fact_id, fact FROM facts_fts WHERE facts_fts MATCH 'quantum OR stress' LIMIT 5")
                    _ = cursor.fetchall()
                elif op_type == 3:
                    # Read: Count and aggregate
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*), AVG(confidence) FROM facts")
                    _ = cursor.fetchone()

                t1 = time.perf_counter()
                thread_latencies.append((t1 - t0) * 1000.0) # in ms

            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower() or "busy" in str(oe).lower():
                    busy_errors.append((thread_id, str(oe)))
                errors.append((thread_id, str(oe)))
            except Exception as ex:
                errors.append((thread_id, str(ex)))

        return thread_latencies

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_task, t_id) for t_id in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            latencies.extend(f.result())

    total_time = time.perf_counter() - start_time
    total_ops = num_threads * ops_per_thread
    tps = total_ops / total_time if total_time > 0 else 0

    p50 = np.percentile(latencies, 50) if latencies else 0
    p95 = np.percentile(latencies, 95) if latencies else 0
    p99 = np.percentile(latencies, 99) if latencies else 0

    print(f"    ├─ Total Wall Time  : {total_time:.2f}s")
    print(f"    ├─ Throughput (TPS) : {tps:.1f} ops/sec")
    print(f"    ├─ Latency (p50)    : {p50:.2f}ms")
    print(f"    ├─ Latency (p95)    : {p95:.2f}ms")
    print(f"    ├─ Latency (p99)    : {p99:.2f}ms")
    print(f"    ├─ Total Errors     : {len(errors)}")
    print(f"    └─ SQLITE_BUSY Hits : {len(busy_errors)} (Goal: 0)")

    return {
        "threads": num_threads,
        "total_ops": total_ops,
        "tps": tps,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "busy_errors": len(busy_errors),
        "total_errors": len(errors)
    }


# ============================================================================
# STAGE 2: TOCTOU ATOMIC FILE INJECTOR COLLISION SIEGE
# ============================================================================
def stage_2_atomic_file_collision_siege(num_writers: int = 20, iterations_per_writer: int = 25):
    print(f"\n[*] [STAGE 2] Launching {num_writers} Concurrent Writers Slamming Target File ({num_writers * iterations_per_writer} writes)...")
    
    STRESS_SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    target_file = STRESS_SCRATCH_DIR / "STRESS_GEMINI.md"
    target_file.write_text("# Initial Protocol\n", encoding="utf-8")

    write_errors = []
    corruption_detected = False
    start_time = time.perf_counter()

    def writer_task(writer_id: int):
        for i in range(iterations_per_writer):
            random_junk = "".join(random.choices(string.ascii_letters + string.digits, k=500))
            payload = f"# PROTOCOL MUTATION - WRITER {writer_id} STEP {i}\nTimestamp: {time.time()}\nData: {random_junk}\n"
            try:
                atomic_write(target_file, payload, retries=5)
            except Exception as e:
                write_errors.append((writer_id, str(e)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_writers) as executor:
        futures = [executor.submit(writer_task, w_id) for w_id in range(num_writers)]
        concurrent.futures.wait(futures)

    total_time = time.perf_counter() - start_time

    # Validate final target file integrity
    if not target_file.exists():
        corruption_detected = True
        final_size = 0
    else:
        final_size = target_file.stat().st_size
        final_content = target_file.read_text(encoding="utf-8", errors="ignore")
        if final_size == 0 or not final_content.startswith("# PROTOCOL MUTATION"):
            corruption_detected = True

    print(f"    ├─ Wall Time        : {total_time:.2f}s")
    print(f"    ├─ Total Collisions : {num_writers * iterations_per_writer} attempts")
    print(f"    ├─ Write Exceptions : {len(write_errors)}")
    print(f"    ├─ Final File Size  : {final_size} bytes")
    print(f"    └─ File Corrupted?  : {'❌ YES (CRITICAL FAILURE)' if corruption_detected else '✅ NO (ZERO CORRUPTION)'}")

    return {
        "writers": num_writers,
        "write_errors": len(write_errors),
        "corrupted": corruption_detected,
        "final_size": final_size
    }


# ============================================================================
# STAGE 3: VECTOR COSINE MATRIX SCALING CLIFF (O(N^2) PROFILER)
# ============================================================================
def stage_3_vector_scaling_cliff():
    print("\n[*] [STAGE 3] Profiling In-Process Numpy Pairwise Cosine Matrix Across Memory Sizes...")
    print("    Investigating the O(N^2) scaling cliff flagged by Claude Sonnet...")
    
    dimensions = 768 # Standard nomic-embed-text / embedding dimension
    test_sizes = [250, 500, 1000, 2500, 5000]
    results = []

    for n in test_sizes:
        # Generate N normalized random embeddings
        matrix = np.random.randn(n, dimensions).astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix = matrix / norms

        t0 = time.perf_counter()
        
        # In-process pairwise cosine similarity computation (Matrix multiplication N x N)
        similarity_matrix = np.dot(matrix, matrix.T)
        
        # Simulate pairwise threshold search for deduplication (similarity > 0.85)
        # Masks out self-similarity (diagonal)
        np.fill_diagonal(similarity_matrix, 0.0)
        duplicates = np.argwhere(similarity_matrix > 0.85)
        
        elapsed = (time.perf_counter() - t0) * 1000.0 # in ms
        mem_mb = similarity_matrix.nbytes / (1024 * 1024)

        print(f"    ├─ N = {n:5d} memories : {elapsed:8.2f}ms | RAM Matrix: {mem_mb:6.2f} MB | {len(duplicates)} duplicate pairs found")
        results.append({"n": n, "time_ms": elapsed, "mem_mb": mem_mb})

    return results


# ============================================================================
# STAGE 4: GRAVEYARD MINER TABOO MATRIX FLOOD & AUTO-RETIREMENT UNDER LOAD
# ============================================================================
def stage_4_graveyard_flood_and_auto_retire(db: ULMDatabase):
    print("\n[*] [STAGE 4] Flooding Graveyard Miner with 500 Simulated Failures & Auto-Retirement...")
    
    conn = db.get_connection()
    cursor = conn.cursor()
    setup_taboo_matrix(cursor)

    sample_errors = [
        ("git push origin main", "The term 'git' is not recognized as the name of a cmdlet"),
        ("python -c \"import json; print('test')\"", "SyntaxError: unterminated string literal (detected at line 1)"),
        ("import torch", "ModuleNotFoundError: No module named 'torch'"),
        ("print(u'\\u2713')", "UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'"),
        ("model.forward()", "OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB"),
        ("print(items[i])", "Array index expression is missing or not valid"),
        ("a, b = [1]", "ValueError: not enough values to unpack (expected 2, got 1)")
    ]

    t0 = time.perf_counter()
    classified_count = 0

    # 1. Flood with 500 executions
    for i in range(500):
        cmd, err = sample_errors[i % len(sample_errors)]
        rule = match_deterministic_heuristic(cmd, err, cursor)
        if rule and "failure_intent" in rule:
            cursor.execute("""
                INSERT INTO taboo_rules (failure_intent, regex_pattern, remediation, last_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(failure_intent) DO UPDATE SET 
                    hit_count = hit_count + 1,
                    last_seen = CURRENT_TIMESTAMP
            """, (rule["failure_intent"], rule.get("regex_pattern", ""), rule.get("remediation", "")))
            classified_count += 1

    # 2. Inject 5 stale rules from 45 days ago to test auto-decay
    for s_idx in range(5):
        stale_intent = f"Stale Obsolete Bug Pattern {s_idx}"
        cursor.execute("""
            INSERT INTO taboo_rules (failure_intent, regex_pattern, remediation, created_at, last_seen)
            VALUES (?, ?, ?, datetime('now', '-45 days'), datetime('now', '-45 days'))
        """, (stale_intent, "obsolete_pattern", "Fix already applied."))

    conn.commit()

    # 3. Trigger 30-Day Auto-Retirement
    retired_count = retire_stale_taboos(cursor, max_age_days=30)
    conn.commit()
    elapsed = (time.perf_counter() - t0) * 1000.0

    print(f"    ├─ Flood Ingestion Time : {elapsed:.2f}ms (for 500 errors)")
    print(f"    ├─ Instant Heuristics   : {classified_count} classified (avg: {elapsed / 500.0:.3f}ms per error)")
    print(f"    ├─ Stale Injected Rules : 5 (dated 45 days ago)")
    print(f"    └─ Auto-Retired Rules   : {retired_count} purged (Goal: 5)")

    return {
        "classified_count": classified_count,
        "retired_count": retired_count,
        "elapsed_ms": elapsed
    }


# ============================================================================
# STAGE 5: COGNITIVE MIRROR PERSONA DEDUPLICATION STRESS
# ============================================================================
def stage_5_persona_deduplication_stress(db: ULMDatabase):
    print("\n[*] [STAGE 5] Stress-Testing Persona Cognitive Mirror Deduplication with 200 Redundant Beliefs...")
    
    conn = db.get_connection()
    cursor = conn.cursor()

    noisy_categories = [
        "Project Directory Structure",
        "project directory structure and workflow organization",
        "Project Workspace and Directory Structure",
        "directory_structure_and_project_management",
        "project_directory_structure",
        "project_directory_structure_and_Vespera's_environment",
        "Work Environment and Tools",
        "workspace organization and utilization",
        "storage strategy and directory structure",
        "engineering_ethos",
        "engineering-ethos-and-surgical-precision",
        "relationship_bond",
        "relationship_bond_with_Bobby",
        "image_synthesis",
        "image_synthesis_and_zit_pipeline",
        "hardware_and_topology",
        "rtx_4070_hardware_topology"
    ]

    for i in range(200):
        cat = noisy_categories[i % len(noisy_categories)]
        s_id = f"stress_schema_{i}"
        belief = f"Belief number {i}: The workstation topology has drives D: and C: configured for high-speed AI tasks."
        conf = 0.5 + (i % 50) * 0.01
        cursor.execute("""
            INSERT OR REPLACE INTO persona_schemas (schema_id, belief_category, current_belief, confidence, last_mutated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (s_id, cat, belief, conf))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM persona_schemas")
    initial_count = cursor.fetchone()[0]

    t0 = time.perf_counter()
    pruned = db.deduplicate_persona_schemas()
    elapsed = (time.perf_counter() - t0) * 1000.0

    cursor.execute("SELECT COUNT(*) FROM persona_schemas")
    final_count = cursor.fetchone()[0]

    print(f"    ├─ Initial Schemas    : {initial_count}")
    print(f"    ├─ Redundant Pruned   : {pruned}")
    print(f"    ├─ Canonical Retained : {final_count}")
    print(f"    └─ Deduplication Time : {elapsed:.2f}ms")

    return {
        "initial": initial_count,
        "pruned": pruned,
        "final": final_count,
        "elapsed_ms": elapsed
    }


# ============================================================================
# MAIN ORCHESTRATION & FINAL TELEMETRY SCORECARD
# ============================================================================
def run_extreme_stress_test():
    print_banner("ULM ADVERSARIAL STRESS TEST & BREAKING POINT RUN")
    cleanup_stress_artifacts()

    db = ULMDatabase(STRESS_DB_PATH)
    db.initialize_db()

    # 1. Concurrency Hammer: 10 Threads
    r10 = stage_1_concurrency_hammer(db, num_threads=10, ops_per_thread=100)

    # 2. Concurrency Hammer: 25 Threads
    r25 = stage_1_concurrency_hammer(db, num_threads=25, ops_per_thread=100)

    # 3. Concurrency Hammer: 50 Threads (The Extreme Redline)
    r50 = stage_1_concurrency_hammer(db, num_threads=50, ops_per_thread=100)

    # 4. Atomic File Collision Siege (20 Threads)
    r_file = stage_2_atomic_file_collision_siege(num_writers=20, iterations_per_writer=25)

    # 5. Vector Scaling Cliff Profiler
    r_vector = stage_3_vector_scaling_cliff()

    # 6. Graveyard Miner Taboo Flood
    r_taboo = stage_4_graveyard_flood_and_auto_retire(db)

    # 7. Persona Deduplication Stress
    r_persona = stage_5_persona_deduplication_stress(db)

    # Close thread connections & clean up
    db.close()
    cleanup_stress_artifacts()

    # ========================================================================
    # FINAL SCORECARD PRESENTATION
    # ========================================================================
    print_banner("STRESS TEST TELEMETRY SCORECARD")
    print(f"{'Test Metric':<35} | {'Result':<22} | {'Status':<15}")
    print("-" * 77)
    
    # Check 1: 50-Thread Concurrency
    c50_status = "✅ PASSED" if r50["busy_errors"] == 0 and r50["total_errors"] == 0 else "❌ FAILED"
    r50_str = f"{r50['tps']:.1f} TPS (p95: {r50['p95']:.1f}ms)"
    print(f"{'50-Thread SQLite WAL Hammer':<35} | {r50_str:<22} | {c50_status:<15}")

    # Check 2: Zero SQLITE_BUSY
    total_busy = r10["busy_errors"] + r25["busy_errors"] + r50["busy_errors"]
    busy_status = "✅ PASSED" if total_busy == 0 else "❌ FAILED"
    busy_str = f"{total_busy} lock errors"
    print(f"{'SQLITE_BUSY Lock Errors':<35} | {busy_str:<22} | {busy_status:<15}")

    # Check 3: Atomic File TOCTOU
    file_status = "✅ PASSED" if not r_file["corrupted"] and r_file["write_errors"] == 0 else "❌ FAILED"
    file_str = f"{r_file['final_size']} bytes intact"
    print(f"{'TOCTOU Atomic Injector (500 ops)':<35} | {file_str:<22} | {file_status:<15}")

    # Check 4: Taboo Auto-Retirement
    taboo_status = "✅ PASSED" if r_taboo["retired_count"] == 5 else "❌ FAILED"
    taboo_str = f"{r_taboo['retired_count']}/5 stale purged"
    print(f"{'Graveyard 30-Day Auto-Decay':<35} | {taboo_str:<22} | {taboo_status:<15}")

    # Check 5: Persona Deduplication
    persona_status = "✅ PASSED" if r_persona["final"] <= 8 else "❌ FAILED"
    persona_str = f"{r_persona['pruned']} pruned ({r_persona['elapsed_ms']:.1f}ms)"
    print(f"{'Cognitive Mirror Deduplication':<35} | {persona_str:<22} | {persona_status:<15}")

    # Check 6: Vector Math Breaking Point Finding
    t5000 = [x["time_ms"] for x in r_vector if x["n"] == 5000][0]
    t5000_str = f"{t5000:.1f} ms"
    cliff_status = "⚠️ CLIFF DETECTED" if t5000 > 1000 else "⚡ SMOOTH"
    print(f"{'N=5,000 Pairwise Cosine Matrix':<35} | {t5000_str:<22} | {cliff_status:<15}")
    print("-" * 77)

    print("\n🏁 STRESS TEST COMPLETE: All systems pushed to extreme load.")


if __name__ == "__main__":
    run_extreme_stress_test()
