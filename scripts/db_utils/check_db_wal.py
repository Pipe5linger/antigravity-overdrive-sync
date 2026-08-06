import os
import sqlite3
import sys

# Target DB Path
DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\db\sync_state.db"

def inspect_and_fix_db(auto_fix: bool = False):
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database file not found at: {DB_PATH}")
        return

    print(f"=== Inspecting Database: {DB_PATH} ===\n")
    try:
        conn = sqlite3.connect(DB_PATH, timeout=2.0)
        cursor = conn.cursor()

        # 1. Journal Mode Check
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = str(cursor.fetchone()[0]).upper()
        print(f"Journal Mode  : {journal_mode}")
        if journal_mode != "WAL":
            print("  [!] WARNING: Database is in rollback mode. Concurrent reads/writes will cause lock stalls.")
        else:
            print("  [✓] OPTIMAL: WAL mode is active.")

        # 2. Busy Timeout Check
        cursor.execute("PRAGMA busy_timeout;")
        busy_timeout = cursor.fetchone()[0]
        print(f"Busy Timeout  : {busy_timeout} ms")
        if busy_timeout == 0:
            print("  [!] WARNING: Timeout is 0ms. Any concurrent write attempt instantly throws 'database is locked'.")
        else:
            print(f"  [✓] Timeout configured to wait {busy_timeout / 1000:.1f} seconds on locks.")

        # 3. Synchronous Mode Check
        cursor.execute("PRAGMA synchronous;")
        sync_mode = cursor.fetchone()[0]
        sync_map = {0: "OFF", 1: "NORMAL (Recommended for WAL)", 2: "FULL", 3: "EXTRA"}
        print(f"Synchronous   : {sync_map.get(sync_mode, sync_mode)}")

        # 4. Immediate Lock Test
        print("\n--- Testing Lock Acquisition ---")
        try:
            cursor.execute("BEGIN IMMEDIATE;")
            print("[✓] SUCCESS: Acquired immediate write lock cleanly.")
            conn.rollback()
        except sqlite3.OperationalError as e:
            print(f"[!] LOCK ERROR: Could not acquire write lock: {e}")

        # Auto-Fix execution if requested
        if auto_fix:
            print("\n--- Applying Optimal Fixes ---")
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=5000;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            conn.commit()
            print("[✓] Applied WAL mode, 5000ms busy timeout, and NORMAL synchronous mode.")

        conn.close()

    except sqlite3.OperationalError as e:
        print(f"\n[CRITICAL LOCK ERROR] Database is locked or inaccessible: {e}")

if __name__ == "__main__":
    # Pass --fix flag to apply WAL and 5000ms timeout automatically
    should_fix = "--fix" in sys.argv
    inspect_and_fix_db(auto_fix=should_fix)