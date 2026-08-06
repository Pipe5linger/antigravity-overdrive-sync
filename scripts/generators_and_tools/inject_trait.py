import sys
import sqlite3
from pathlib import Path

# Base Path Resolution (Target: D:\AI\Projects\antigravity-overdrive-sync)
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "db" / "sync_state.db"


def inject_trait(category: str, trait: str) -> bool:
    """
    Safely injects a new trait or memory into sync_state.db.
    Includes a 10-second retry timeout so it doesn't collide with sync_engine passes.
    """
    if not DB_PATH.exists():
        print(f"[-] [Injector Error] Target database not found at: {DB_PATH}")
        return False

    try:
        # timeout=10.0 waits up to 10 seconds if sync_engine is active or vacuuming
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()

        # Insert new trait entry into target persona_profile table (category, trait)
        cursor.execute(
            """
            INSERT INTO persona_profile (category, trait)
            VALUES (?, ?)
            """,
            (category.strip(), trait.strip())
        )

        conn.commit()
        conn.close()
        print(f"[+] [Injector] Successfully wrote trait to '{category}': {trait[:50]}...")
        return True

    except sqlite3.OperationalError as e:
        print(f"[-] [Injector Error] Vault error: {e}")
        return False
    except Exception as e:
        print(f"[-] [Injector Error] Failed to write trait: {e}")
        return False


if __name__ == "__main__":
    # Allows direct CLI testing: python inject_trait.py "Category" "Trait text"
    if len(sys.argv) >= 3:
        cat = sys.argv[1]
        trt = sys.argv[2]
        inject_trait(cat, trt)
    else:
        print("Usage: python inject_trait.py <category> <trait>")