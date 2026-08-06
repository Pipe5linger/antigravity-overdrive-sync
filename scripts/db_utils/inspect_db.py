import sqlite3

DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\db\sync_state.db"

def inspect():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    print("================================================================================")
    print(f"[*] TABLES IN {DB_PATH}:")
    print("================================================================================")

    for t in tables:
        table_name = t[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        row_count = cursor.fetchone()[0]
        print(f"\n[Table] {table_name} (Rows: {row_count})")
        
        cursor.execute(f"PRAGMA table_info({table_name});")
        cols = cursor.fetchall()
        for col in cols:
            print(f"  ├── {col[1]} ({col[2]})")

    conn.close()

if __name__ == "__main__":
    inspect()