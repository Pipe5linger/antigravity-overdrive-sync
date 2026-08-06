import os
import sys
import atexit
import sqlite3

LOCK_FILE = "dedupe_conversations.lock"

# ------------------------------------------------------------------
# Safe Lock File Setup
# Prevents duplicate execution while guaranteeing cleanup on exit/crash.
# ------------------------------------------------------------------
if os.path.exists(LOCK_FILE):
    print(f"[-] Lock file '{LOCK_FILE}' exists. Another instance may be running. Aborting.")
    sys.exit(1)

try:
    with open(LOCK_FILE, 'w', encoding='utf-8') as f:
        f.write(str(os.getpid()))
except Exception as e:
    print(f"[-] Failed to create lock file: {e}")
    sys.exit(1)

def cleanup_lock():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass

# Register automatic cleanup on process termination
atexit.register(cleanup_lock)

# ------------------------------------------------------------------
# Atomic Database Operations
# ------------------------------------------------------------------
def update_vespera_memory(traits, db_filename):
    """
    Inserts or updates persona profile traits into the target SQLite database.
    Uses Python's built-in sqlite3 context manager ('with conn:') to handle
    BEGIN, COMMIT, and ROLLBACK operations automatically and safely.
    """
    if not traits:
        return 0
    
    inserted = 0
    try:
        with sqlite3.connect(db_filename) as conn:
            cursor = conn.cursor()
            
            for trait in traits:
                category = trait.get('category', 'lore').lower()
                trait_name = trait.get('trait')
                confidence = float(trait.get('confidence', 0.8))
                
                if not trait_name:
                    continue
                
                cursor.execute("""
                    INSERT INTO persona_profile (category, trait, confidence, frequency)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(trait) DO UPDATE SET 
                        frequency = frequency + 1,
                        confidence = MAX(confidence, excluded.confidence)
                """, (category, trait_name, confidence))
                
                inserted += 1

    except Exception as e:
        print(f"[-] Database insertion choke for {db_filename}: {e}")
        return 0
    
    return inserted

# ------------------------------------------------------------------
# Main Execution Routine
# ------------------------------------------------------------------
def run_deep_sweep():
    print("[+] Initializing deep sweep for conversation databases...")
    # Add conversation parsing and trait extraction routines here.
    print("[+] Deep sweep completed successfully.")

if __name__ == "__main__":
    try:
        run_deep_sweep()
    except Exception as e:
        print(f"[-] Unhandled exception during deep sweep: {e}")
        sys.exit(1)