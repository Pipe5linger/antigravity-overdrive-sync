import os
import sys
import sqlite3
from pathlib import Path

# Target project directory and DB
PROJECT_DIR = Path(r"D:\AI\Projects\antigravity-overdrive-sync")
TARGET_DB = PROJECT_DIR / "db" / "sync_state.db"

# Test Payload
TEST_CATEGORY = "__DIAGNOSTIC_TEST__"
TEST_TRAIT = "Automated path and output test payload"


def test_path_and_output():
    print("=========================================")
    print("      INJECTOR DIAGNOSTIC TEST RUNNER    ")
    print("=========================================\n")

    # 1. Force execution context to foreign directory (C:\) to test relative path leaks
    foreign_dir = Path("C:/")
    os.chdir(foreign_dir)
    print(f"[*] Simulated Execution Directory: {os.getcwd()}")
    print(f"[*] Target Database Path: {TARGET_DB}\n")

    # 2. Import target injector module from explicit project path
    sys.path.insert(0, str(PROJECT_DIR))
    try:
        import inject_trait
    except ImportError:
        print("[-] Error: Could not locate 'inject_trait.py' in project path!")
        return

    # 3. Execute Injection Test
    print("[*] Executing injection write...")
    success = inject_trait.inject_trait(TEST_CATEGORY, TEST_TRAIT)
    
    if not success:
        print("[-] Injection function reported failure.")
        return

    # 4. Verify Output in SQLite
    print("\n[*] Verifying database output directly in SQLite...")
    try:
        conn = sqlite3.connect(TARGET_DB)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT category, trait FROM persona_profile WHERE category = ?",
            (TEST_CATEGORY,)
        )
        row = cursor.fetchone()
        
        if row:
            cat, trait = row
            print(f"[+] SUCCESS: Record verified in target database!")
            print(f"    - Category: {cat}")
            print(f"    - Trait: {trait}\n")
            
            # Clean up test row
            cursor.execute("DELETE FROM persona_profile WHERE category = ?", (TEST_CATEGORY,))
            conn.commit()
            print("[+] Test payload cleaned up from database.")
        else:
            print("[-] FAIL: Injection reported success, but record was not found in target database!")

        conn.close()

    except Exception as e:
        print(f"[-] Database query error during verification: {e}")

    # 5. Check for Phantom Files in Foreign Directory
    phantom_db = foreign_dir / "db"
    if phantom_db.exists():
        print(f"\n[!] WARNING: Phantom directory detected at '{phantom_db}'!")
        print("    Your injector is still using a relative path somewhere in its write loop.")
    else:
        print("\n[+] PATH TEST PASSED: No rogue database files created in working directory.")


if __name__ == "__main__":
    test_path_and_output()