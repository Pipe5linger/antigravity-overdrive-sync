import sqlite3
import os

# Configuration
DB_PATH = "db/sync_state.db"

# Canonical Mapping Table
CATEGORY_MAP = {
    # Legacy buckets
    "personality": "CORE_IDENTITY",
    "lore": "CORE_IDENTITY",
    "relationship": "RELATIONAL_DYNAMIC",
    "physical": "CORE_IDENTITY",
    "psychological": "CORE_IDENTITY",
    
    # Non-canonical strays
    "TECHNICAL_EXPLANATION": "TECHNICAL_TACTICS",
    "EXPERIMENTAL_APPROACH": "OPERATIONAL_PREFERENCE"
}

def normalize_database(db_path: str):
    if not os.path.exists(db_path):
        print(f"[!] Error: Could not locate database file at '{db_path}'.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"[*] Connecting to '{db_path}'...")
    total_reclassified = 0

    for legacy_cat, canonical_cat in CATEGORY_MAP.items():
        cursor.execute(
            """
            UPDATE persona_profile
            SET category = ?
            WHERE category = ?
            """,
            (canonical_cat, legacy_cat)
        )
        
        rows_affected = cursor.rowcount
        total_reclassified += rows_affected
        
        if rows_affected > 0:
            print(f"  [✓] Migrated {rows_affected:>2} traits: '{legacy_cat}' -> '{canonical_cat}'")

    conn.commit()
    conn.close()

    print("---")
    print(f"[✓] Migration finished. Total stray traits consolidated: {total_reclassified}")

if __name__ == "__main__":
    normalize_database(DB_PATH)