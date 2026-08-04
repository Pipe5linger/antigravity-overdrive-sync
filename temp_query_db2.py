import sqlite3

db_path = r"D:\\AI\\Projects\\antigravity-overdrive-sync\\sync_state.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# List tables
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', tables)

# Count rows in persona_profile
try:
    count_profile = c.execute('SELECT COUNT(*) FROM persona_profile').fetchone()[0]
    print('persona_profile row count:', count_profile)
except Exception as e:
    print('Error querying persona_profile:', e)

# Count rows in persona_schemas
try:
    count_schemas = c.execute('SELECT COUNT(*) FROM persona_schemas').fetchone()[0]
    print('persona_schemas row count:', count_schemas)
except Exception as e:
    print('Error querying persona_schemas:', e)

conn.close()
