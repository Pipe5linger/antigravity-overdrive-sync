import sqlite3
import os

SYNC_DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\sync_state.db"

def inspect_persona_vault():
    if not os.path.exists(SYNC_DB_PATH):
        print(f"[-] Database not found at {SYNC_DB_PATH}")
        return

    conn = sqlite3.connect(SYNC_DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, category, trait, confidence, frequency, project_tag, last_seen 
            FROM persona_profile 
            ORDER BY frequency DESC, confidence DESC
        """)
        rows = cursor.fetchall()

        print("=" * 90)
        print(f"VESPERA PERSONA VAULT — TOTAL UNIQUE TRAITS: {len(rows)}")
        print("=" * 90)

        if not rows:
            print("[-] No traits currently stored in persona_profile.")
            return

        for row in rows:
            trait_id, category, trait, confidence, frequency, tag, last_seen = row
            print(f"[{trait_id}] [{category.upper()}] (Freq: {frequency} | Conf: {confidence:.2f} | Tag: {tag})")
            print(f"    Trait: {trait}")
            print(f"    Last Seen: {last_seen}")
            print("-" * 90)

    except Exception as e:
        print(f"[-] Error querying persona_profile table: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_persona_vault()