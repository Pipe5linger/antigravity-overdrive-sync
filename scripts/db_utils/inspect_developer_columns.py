import sqlite3

DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\db\sync_state.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get column details
cursor.execute("PRAGMA table_info(developer_profile);")
columns = cursor.fetchall()

print("=" * 60)
print(f"COLUMNS IN {DB_PATH} -> 'developer_profile'")
print("=" * 60)
for col in columns:
    # col format: (cid, name, type, notnull, dflt_value, pk)
    print(f"Column ID: {col[0]} | Name: '{col[1]}' | Type: {col[2]}")

print("=" * 60)

# Grab 1 sample row to see real key/value pairs
cursor.execute("SELECT * FROM developer_profile LIMIT 1;")
sample_row = cursor.fetchone()
print("SAMPLE ROW:")
print(sample_row)
print("=" * 60)

conn.close()