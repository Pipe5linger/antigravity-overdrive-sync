import os
import sqlite3

ROOT_DB = r"D:\AI\Projects\antigravity-overdrive-sync\sync_state.db"
TARGET_DB = r"D:\AI\Projects\antigravity-overdrive-sync\db\sync_state.db"

def run_migration():
    conn = sqlite3.connect(TARGET_DB)
    cursor = conn.cursor()

    print("[*] Starting Persona Migration & Schema Parity Pass...")

    # 1. Attach Root DB if persona_profile needs to be pulled over
    if os.path.exists(ROOT_DB):
        print(f" [+] Attaching root vault: {ROOT_DB}")
        cursor.execute(f"ATTACH DATABASE '{ROOT_DB}' AS root_db;")
        
        # Check if persona_profile exists in root_db
        cursor.execute("SELECT name FROM root_db.sqlite_master WHERE type='table' AND name='persona_profile';")
        if cursor.fetchone():
            print(" [+] Copying 'persona_profile' into main db/sync_state.db...")
            cursor.execute("CREATE TABLE IF NOT EXISTS persona_profile AS SELECT * FROM root_db.persona_profile WHERE 0;")
            cursor.execute("INSERT OR IGNORE INTO persona_profile SELECT * FROM root_db.persona_profile;")
            conn.commit()  # Commit transaction to release read lock
            print(" [✔] persona_profile successfully migrated!")
        
        try:
            cursor.execute("DETACH DATABASE root_db;")
        except sqlite3.OperationalError:
            pass  # Closing connection will automatically detach cleanly

    # 2. Upgrade developer_profile with Persona fields
    dev_columns_to_add = [
        ("weight", "REAL DEFAULT 1.0"),
        ("evolution_stage", "TEXT DEFAULT 'STABLE'"),
        ("emotional_context", "TEXT DEFAULT 'NEUTRAL'"),
        ("source_session", "TEXT")
    ]

    cursor.execute("PRAGMA table_info(developer_profile);")
    existing_dev_cols = [col[1] for col in cursor.fetchall()]

    for col_name, col_type in dev_columns_to_add:
        if col_name not in existing_dev_cols:
            print(f" [+] Upgrading developer_profile -> Adding '{col_name}'...")
            cursor.execute(f"ALTER TABLE developer_profile ADD COLUMN {col_name} {col_type};")

    # 3. Upgrade persona_profile with Developer fields
    persona_columns_to_add = [
        ("frequency", "INTEGER DEFAULT 1"),
        ("emotional_context", "TEXT DEFAULT 'NEUTRAL'"),
        ("source_session", "TEXT")
    ]

    cursor.execute("PRAGMA table_info(persona_profile);")
    existing_persona_cols = [col[1] for col in cursor.fetchall()]

    for col_name, col_type in persona_columns_to_add:
        if col_name not in existing_persona_cols:
            print(f" [+] Upgrading persona_profile -> Adding '{col_name}'...")
            cursor.execute(f"ALTER TABLE persona_profile ADD COLUMN {col_name} {col_type};")

    conn.commit()
    conn.close()
    print("\n================================================================================")
    print("[✔] DUAL-ENGINE PARITY COMPLETE: Both profiles now unified in db/sync_state.db!")
    print("================================================================================")

if __name__ == "__main__":
    run_migration()