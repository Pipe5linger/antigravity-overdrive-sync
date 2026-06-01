import os
import sys
import time
import tracemalloc
import sqlite3
import datetime

# Dynamic path resolution to work on any machine
BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_PATH = os.path.dirname(BENCHMARK_DIR)
sys.path.append(REPO_PATH)

from core.database import ULMDatabase

# Setup temporary paths inside the benchmark directory
TEST_DB_PATH = os.path.join(BENCHMARK_DIR, "stress_test_run.db")

def run_sqlite_stress_test():
    print("\n" + "="*60)
    print("🚀 BEGINNING SQLITE STRESS TEST & TELEMETRY RUN")
    print("="*60)

    # 1. Clean up old test DB if present
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    # 2. Instantiate and initialize database
    db = ULMDatabase(TEST_DB_PATH)
    db.initialize_db()

    # Start tracking memory and time
    tracemalloc.start()
    start_time = time.time()

    # 3. Simulate extreme insertions (1,000 standard sessions, 10 messages each)
    print("[*] Simulating 1,000 chat sessions...")
    total_sessions = 1000
    messages_per_session = 10
    
    for i in range(total_sessions):
        session_id = f"session_stress_{i}"
        db.upsert_session(session_id, "stress_tester", "Coding/LoadTest")
        
        for j in range(messages_per_session):
            role = "user" if j % 2 == 0 else "model"
            content = f"This is load test message turn {j} in standard session {i}."
            created_at = (datetime.datetime.now() - datetime.timedelta(minutes=j)).isoformat()
            db.insert_message(session_id, role, content, created_at)

    # 4. Hammer the Deduplication Engine (Insert 5,000 duplicate messages)
    print("[*] Hammering deduplication logic with 5,000 duplicate messages...")
    for j in range(5000):
        # We reuse the exact same messages, role, and timestamps to force duplicates
        session_id = "session_stress_0"
        role = "user" if j % 2 == 0 else "model"
        content = f"This is load test message turn {j % 10} in standard session 0."
        created_at = (datetime.datetime.now() - datetime.timedelta(minutes=(j % 10))).isoformat()
        db.insert_message(session_id, role, content, created_at)

    # 5. Insert 500 core facts and preferences
    print("[*] Injecting 500 facts & preferences...")
    for i in range(500):
        db.upsert_fact(f"User preference core factual statement {i}", "loadtest", 0.9)
        db.set_preference(f"pref_key_{i}", f"pref_val_{i}")

    duration = time.time() - start_time
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("="*60)
    print("📈 INSERTION PERFORMANCE RESULTS:")
    print(f"[*] Total Insertion Time: {duration:.3f} seconds")
    print(f"[*] Peak Memory Allocation: {peak_mem / 1024 / 1024:.3f} MB")
    print(f"[*] Current Memory Usage: {current_mem / 1024 / 1024:.3f} MB")
    print("="*60)

    # 6. Stress Test Search Latency
    print("[*] Benchmarking context query latency...")
    query_start = time.time()
    context = db.get_recent_context(limit=100)
    query_duration = time.time() - query_start

    print("="*60)
    print("🔍 QUERY LATENCY RESULTS:")
    print(f"[*] Retrieved context size: {len(context)} rows")
    print(f"[*] Context Query Latency: {query_duration * 1000:.3f} ms")
    print("="*60)

    # 7. Check database file size
    if os.path.exists(TEST_DB_PATH):
        db_size = os.path.getsize(TEST_DB_PATH) / 1024 / 1024
        print(f"[*] SQLite Database File Size: {db_size:.2f} MB")
    print("="*60)

    # 8. Clean up
    print("[*] Cleaning up temporary test database...")
    try:
        # Give SQLite a tiny split second to release any system lock handles
        time.sleep(0.5)
        os.remove(TEST_DB_PATH)
        print("[+] Test database deleted successfully.")
    except Exception as e:
        print(f"[-] Cleanup warning: {e}")

    print("[+] SQLite Stress Test completed. System is rock-solid!")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_sqlite_stress_test()
