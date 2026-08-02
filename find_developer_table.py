import os
import sqlite3

SEARCH_DIRS = [
    r"D:\AI\Projects",
    r"C:\Users\boben\.gemini\antigravity",
]

def check_db_for_developer_table(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        for table in tables:
            if "developer" in table.lower() or "profile" in table.lower():
                return table, tables
    except Exception:
        pass
    return None, []

print("[*] Scanning for SQLite databases containing developer profile tables...\n")

found_count = 0
for search_dir in SEARCH_DIRS:
    if not os.path.exists(search_dir):
        continue
    for root, dirs, files in os.walk(search_dir):
        for file in files:
            if file.endswith(".db") and not file.endswith("-shm") and not file.endswith("-wal"):
                full_path = os.path.join(root, file)
                matched_table, all_tables = check_db_for_developer_table(full_path)
                if matched_table:
                    found_count += 1
                    print(f"==================================================")
                    print(f"[!] FOUND MATCH: {full_path}")
                    print(f"    Target Table : '{matched_table}'")
                    print(f"    All Tables   : {all_tables}")
                    print(f"==================================================\n")

if found_count == 0:
    print("[-] No database with a developer profile table was found in the search directories.")