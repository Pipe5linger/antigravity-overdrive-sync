import sqlite3
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "db" / "sync_state.db"
BACKUP_PATH = BASE_DIR / "db" / "sync_state.db.bak"

def deduplicate_vault():
    if not DB_PATH.exists():
        print(f"[-] [Dedupe Error] Database not found at {DB_PATH}")
        return

    # 1. Create a safety backup before modifying
    print(f"[*] [Dedupe Engine] Creating backup at {BACKUP_PATH.name}...")
    shutil.copy2(DB_PATH, BACKUP_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Inspect columns dynamically
        cursor.execute("PRAGMA table_info(persona_profile)")
        columns = [col[1] for col in cursor.fetchall()]
        
        category_col = "category" if "category" in columns else columns[1]
        trait_col = next((c for c in ["trait_description", "trait", "description", "value", "trait_name"] if c in columns), columns[2])
        freq_col = "frequency" if "frequency" in columns else None
        conf_col = "confidence" if "confidence" in columns else None

        print(f"[*] [Dedupe Engine] Deduplicating on: {category_col} + LOWER({trait_col})...")

        cursor.execute("SELECT COUNT(*) FROM persona_profile")
        initial_count = cursor.fetchone()[0]

        # 2. Consolidate Frequency and Confidence before deleting duplicate rows
        if freq_col and conf_col:
            update_query = f"""
            UPDATE persona_profile
            SET {freq_col} = (
                SELECT SUM(sub.{freq_col}) 
                FROM persona_profile sub 
                WHERE LOWER(sub.{category_col}) = LOWER(persona_profile.{category_col})
                  AND LOWER(sub.{trait_col}) = LOWER(persona_profile.{trait_col})
            ),
            {conf_col} = (
                SELECT MAX(sub.{conf_col}) 
                FROM persona_profile sub 
                WHERE LOWER(sub.{category_col}) = LOWER(persona_profile.{category_col})
                  AND LOWER(sub.{trait_col}) = LOWER(persona_profile.{trait_col})
            )
            WHERE rowid IN (
                SELECT MIN(rowid)
                FROM persona_profile
                GROUP BY LOWER({category_col}), LOWER({trait_col})
            );
            """
            cursor.execute(update_query)

        # 3. Delete secondary duplicate rows (keeping the row with the lowest rowid)
        delete_query = f"""
        DELETE FROM persona_profile
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM persona_profile
            GROUP BY LOWER({category_col}), LOWER({trait_col})
        );
        """
        cursor.execute(delete_query)
        deleted_count = cursor.rowcount

        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM persona_profile")
        final_count = cursor.fetchone()[0]

        # 4. Reclaim disk space and optimize database structure
        print("[*] [Dedupe Engine] Vacuuming database...")
        cursor.execute("VACUUM;")

        print("\n[+] Deduplication complete!")
        print(f"    - Initial rows: {initial_count}")
        print(f"    - Duplicates purged: {deleted_count}")
        print(f"    - Final active traits: {final_count}")

    except Exception as e:
        print(f"[-] [Dedupe Error] Transaction failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    deduplicate_vault()