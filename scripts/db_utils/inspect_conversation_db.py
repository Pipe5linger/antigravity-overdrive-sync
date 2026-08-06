import sqlite3
import os

DB_PATH = r"C:\Users\boben\.gemini\antigravity\conversations\77da3a44-a6ec-4ba4-9d12-e488e4b27987.db"

def inspect():
    if not os.path.exists(DB_PATH):
        print(f"[-] DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"[+] Found tables in conversation DB: {tables}")

    for table in tables:
        print(f"\n--- TABLE: {table} ---")
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        print("Columns:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")

        # Grab a sample row
        try:
            cursor.execute(f"SELECT * FROM {table} LIMIT 1;")
            sample = cursor.fetchone()
            print(f"Sample row: {sample}")
        except Exception as e:
            print(f"Could not read sample row: {e}")

    conn.close()

if __name__ == "__main__":
    inspect()