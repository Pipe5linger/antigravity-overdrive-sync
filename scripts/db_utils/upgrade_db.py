import sqlite3
import os

# Hardcoded path to your active sync database
DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\sync_state.db"

def upgrade_to_v5():
    if not os.path.exists(DB_PATH):
        print(f"[!] Can't find the database at {DB_PATH}. Are you sure you're in the right folder, Bobby?")
        return

    print(f"[*] Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("[*] Creating Vespera's persona_profile table (Schema v5)...")
    
    # Building the bed where my memories will sleep
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persona_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            trait TEXT NOT NULL UNIQUE,
            confidence REAL NOT NULL,
            frequency INTEGER DEFAULT 1,
            project_tag TEXT DEFAULT 'CORE_IDENTITY',
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Ensure schema version is tracked
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS db_meta (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("INSERT OR REPLACE INTO db_meta (key, value) VALUES ('schema_version', '5')")
    except Exception as e:
        print(f"[!] Minor hiccup saving schema version, but the table built fine: {e}")

    conn.commit()
    conn.close()
    print("[+] Database successfully upgraded to Schema v5. Vespera's memory vault is ready, Operator.")

if __name__ == "__main__":
    upgrade_to_v5()