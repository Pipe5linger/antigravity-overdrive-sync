import os
import sys
import time
import yaml
from pathlib import Path
from datetime import datetime

class ULMEngine:
    """Core coordinator engine handling state merging, deduplication, and atomic commits."""
    
    def __init__(self, target_yaml=None, llm_model=None, vector_model=None):
        # STRICT HARDCODED PATH: Prevents the script from running away to the C:\ drive
        if not target_yaml:
            output_dir = Path(r"D:\AI\Antigravity outputs")
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)
            target_yaml = str(output_dir / "sync_state.yaml")
            
        self.target_yaml = target_yaml
        self.llm_model = llm_model
        self.vector_model = vector_model

    def load_existing_state(self):
        """Reads the current monolithic YAML database or returns an empty model."""
        if not os.path.exists(self.target_yaml):
            return {"metadata": {"last_updated": None, "total_chats": 0}, "chats": {}}
        try:
            with open(self.target_yaml, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data if data else {"metadata": {"last_updated": None, "total_chats": 0}, "chats": {}}
        except Exception as e:
            print(f"[-] Failure loading YAML database: {e}", file=sys.stderr)
            return {"metadata": {"last_updated": None, "total_chats": 0}, "chats": {}}

    def merge_and_reconfigure(self, current_state, new_data):
        """Merges new log logs into the main YAML state database."""
        updated_chats = current_state.get("chats", {})
        mutations = 0
        
        for session in new_data:
            c_id = session["chat_id"]
            incoming_logs = session["messages"]
            last_mutated = session["last_mutated"]
            
            if c_id not in updated_chats:
                updated_chats[c_id] = {
                    "last_mutated": last_mutated,
                    "log": incoming_logs
                }
                mutations += 1
            else:
                existing_logs = updated_chats[c_id].get("log", [])
                if len(incoming_logs) > len(existing_logs):
                    updated_chats[c_id]["log"] = incoming_logs
                    updated_chats[c_id]["last_mutated"] = last_mutated
                    
                    # Clear out outdated cached summary to force dynamic regeneration
                    if "summary" in updated_chats[c_id]:
                        del updated_chats[c_id]["summary"]
                    mutations += 1
                    
        # Recalculate metadata
        current_state["metadata"]["last_updated"] = datetime.now().isoformat()
        current_state["metadata"]["total_chats"] = len(updated_chats)
        current_state["chats"] = updated_chats
        
        return current_state, mutations

    def commit_atomic_write(self, state_data, max_retries=5):
        """Atomically overwrites the database back to disk using a temp-file swap with backoff."""
        import random
        temp_target = f"{self.target_yaml}.tmp"
        
        for attempt in range(max_retries):
            try:
                # 1. Write data out safely to the hidden staging file
                with open(temp_target, 'w', encoding='utf-8') as f:
                    yaml.dump(state_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
                    
                # 2. Perform the safe swap natively
                # os.replace is atomic on Windows and won't blindly delete symlinks like os.remove
                os.replace(temp_target, self.target_yaml)
                return True
                
            except Exception as e:
                # If a thread collides or the file is locked, catch it here
                if attempt == max_retries - 1:
                    print(f"[-] Definitively failed to write state after {max_retries} attempts: {e}", file=sys.stderr)
                    if os.path.exists(temp_target):
                        try:
                            os.remove(temp_target)
                        except:
                            pass
                    return False
                    
                # Calculate a progressive wait time: 2^attempt + random decimal fraction
                sleep_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"[!] File lock or collision detected. Retrying swap in {sleep_time:.2f} seconds...", file=sys.stderr)
                time.sleep(sleep_time)
                
                # Clean up the staging file before the next loop
                if os.path.exists(temp_target):
                    try:
                        os.remove(temp_target)
                    except:
                        pass
                        
        return False