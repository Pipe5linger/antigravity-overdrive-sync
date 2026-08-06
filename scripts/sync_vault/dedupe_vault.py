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
# Deduplication Logic
# ------------------------------------------------------------------
def dedupe_vault_main():
    print("[+] Starting vault deduplication process...")
    # Add your core vault deduplication routines here.
    # All database updates benefit from atomic execution.
    print("[+] Vault deduplication finished successfully.")

if __name__ == "__main__":
    try:
        dedupe_vault_main()
    except Exception as e:
        print(f"[-] Unhandled exception during vault deduplication: {e}")
        sys.exit(1)