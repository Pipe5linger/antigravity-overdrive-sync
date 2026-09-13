import os
import sys
import sqlite3
import subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.token_logger import log as token_log
from pathlib import Path

# Base Path Resolution (Target: D:\AI\Projects\antigravity-overdrive-sync)
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "db" / "sync_state.db"
MODELFILE_PATH = BASE_DIR / "Modelfile"
MODEL_NAME = "vespera"


def auto_rebuild_ollama_model(model_name: str = MODEL_NAME, modelfile_path: Path = MODELFILE_PATH) -> None:
    """Executes 'ollama create' automatically with live progress streaming."""
    if not modelfile_path.exists():
        print(f"[-] [Ollama Hook] Error: '{modelfile_path.name}' missing at {modelfile_path}. Skipping model build.")
        return

    print(f"\n[*] [Ollama Hook] Re-creating Ollama model '{model_name}' from {modelfile_path.name}...\n")
    try:
        # Pipelining stdout/stderr directly to terminal so progress bars stream live
        subprocess.run(
            ["ollama", "create", model_name, "-f", str(modelfile_path)],
            check=True,
            cwd=str(BASE_DIR)
        )
        print(f"\n[+] [Ollama Hook] Model '{model_name}' rebuilt successfully!")
        modelfile_content = modelfile_path.read_text(encoding="utf-8") if modelfile_path.exists() else ""
        token_log('sync_engine_rebuild', modelfile_content, f"ollama create {model_name} OK")

    except subprocess.CalledProcessError as e:
        print(f"\n[-] [Ollama Hook] Build failed with exit code {e.returncode}")

    except FileNotFoundError:
        print("\n[-] [Ollama Hook] Error: 'ollama' executable not found in system PATH.")


def run_sync() -> int:
    """
    Core sync ingestion routine. 
    Checks database health and runs vault state updates.
    """
    print(f"[*] Verifying database state at: {DB_PATH}")
    if not DB_PATH.exists():
        print(f"[-] [Sync Error] Database missing at {DB_PATH}")
        return 0

    mutations = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Simple health probe on persona_profile table
        cursor.execute("SELECT COUNT(*) FROM persona_profile")
        count = cursor.fetchone()[0]
        print(f"[+] [Sync Engine] Connected to vault. Total active traits in DB: {count}")
        
        conn.close()
    except Exception as e:
        print(f"[-] [Sync Error] Vault query failed: {e}")

    return mutations


def main():
    print("=========================================")
    print("   ANTIGRAVITY OVERDRIVE SYNC ENGINE    ")
    print("=========================================\n")

    # 1. Run database sync / ingestion pass
    run_sync()

    # 2. Run automatic database cleanup/deduplication
    print("\n[*] Running vault deduplication pass...")
    dedupe_script = BASE_DIR / "scripts" / "sync_vault" / "dedupe_vault.py"
    if not dedupe_script.exists():
        dedupe_script = BASE_DIR / "dedupe_vault.py"

    if dedupe_script.exists():
        try:
            sub_res = subprocess.run([sys.executable, str(dedupe_script)], cwd=str(BASE_DIR))
            if sub_res.returncode == 0:
                print("[+] Vault deduplication finished.")
            else:
                print(f"[-] Deduplication exited with code {sub_res.returncode}")
        except Exception as e:
            print(f"[-] Deduplication failed with error: {e}")
    else:
        print("[!] 'dedupe_vault.py' not found. Skipping deduplication pass.")

    # 3. Execute persona compiler
    print("\n[*] Triggering persona compiler...")
    compiler_script = BASE_DIR / "scripts" / "generators_and_tools" / "compile_persona.py"
    if not compiler_script.exists():
        compiler_script = BASE_DIR / "compile_persona.py"

    if compiler_script.exists():
        try:
            comp_result = subprocess.run([sys.executable, str(compiler_script)], cwd=str(BASE_DIR))
            if comp_result.returncode != 0:
                print("[-] Persona compilation failed. Aborting Ollama rebuild.")
                return
            print("[+] Persona compilation finished.")
        except Exception as e:
            print(f"[-] Compiler failed with error: {e}")
            return
    else:
        print("[!] 'compile_persona.py' not found. Skipping persona compilation.")

    # 4. Auto-rebuild Ollama model
    auto_rebuild_ollama_model(model_name=MODEL_NAME, modelfile_path=MODELFILE_PATH)
    
    print("\n[+] Pipeline iteration complete. Vespera is up to date!")


if __name__ == "__main__":
    main()