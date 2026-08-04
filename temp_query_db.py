import sqlite3

db_path = r"D:\\AI\\Projects\\antigravity-overdrive-sync\\sync_state.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# List tables
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)

# Query persona_profile
try:
    profile_rows = c.execute("SELECT * FROM persona_profile").fetchall()
    print("persona_profile rows:", profile_rows)
except Exception as e:
    print("Error querying persona_profile:", e)

# Query persona_schemas (Cognitive Mirror)
try:
    schemas_rows = c.execute("SELECT * FROM persona_schemas").fetchall()
    print("persona_schemas rows:", schemas_rows)
except Exception as e:
    print("Error querying persona_schemas:", e)

conn.close()
