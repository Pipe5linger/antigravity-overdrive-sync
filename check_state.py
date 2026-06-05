import sqlite3
import os
import json

db_path = os.path.join(os.environ['APPDATA'], 'Code', 'User', 'globalStorage', 'state.vscdb')

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT value FROM itemTable WHERE key = 'RooVeterinaryInc.roo-cline'")
        row = c.fetchone()
        if row:
            parsed = json.loads(row[0])
            print(json.dumps(parsed, indent=2))
        else:
            print("Key RooVeterinaryInc.roo-cline not found.")
    except Exception as e:
        print(f"Error reading SQLite: {e}")
else:
    print("Database file does not exist.")
