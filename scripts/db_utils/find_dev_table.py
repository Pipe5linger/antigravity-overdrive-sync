import os
import sqlite3

search_dirs = [
    r"D:\AI\Projects\antigravity-overdrive-sync",
    r"C:\Users\boben\.gemini\antigravity",
    r"C:\Users\boben\.gemini\antigravity\conversations"
]

print("=== SEARCHING FOR DEVELOPER TABLES IN SQLITE DBs ===")

for s_dir in search_dirs:
    if not os.path.exists(s_dir):
        continue
    for root, _, files in os.walk(s_dir):
        for f in files:
            if f.endswith(".db") and not f.endswith("-shm") and not f.endswith("-wal"):
                db_path = os.path.join(root, f)
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = [t[0] for t in cursor.fetchall()]
                    
                    # Look for tables with 'developer', 'profile', or 'persona' in the name
                    matching_tables = [t for t in tables if any(k in t.lower() for k in ['developer', 'profile', 'metric', 'vault'])]
                    if matching_tables:
                        print(f"\n[FOUND] Database: {db_path}")
                        for t in matching_tables:
                            print(f"  └── Table: {t}")
                            # Inspect column names
                            cursor.execute(f"PRAGMA table_info({t});")
                            cols = [c[1] for c in cursor.fetchall()]
                            print(f"      Columns: {cols}")
                    conn.close()
                except Exception:
                    pass