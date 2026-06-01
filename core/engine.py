import os
import sys
import yaml
from datetime import datetime

class ULMEngine:
    """Core coordinator engine handling state merging, deduplication, and atomic commits."""
    
    def __init__(self, target_yaml=None):
        if not target_yaml:
            USER_HOME = os.path.expanduser("~")
            output_dir = os.path.join(USER_HOME, "Desktop", "Antigravity outputs")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            target_yaml = os.path.join(output_dir, "sync_state.yaml")
        self.target_yaml = target_yaml
        
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
                    mutations += 1

        # Recalculate metadata
        current_state["metadata"]["last_updated"] = datetime.now().isoformat()
        current_state["metadata"]["total_chats"] = len(updated_chats)
        current_state["chats"] = updated_chats
        
        return current_state, mutations
        
    def commit_atomic_write(self, state_data):
        """Atomically overwrites the database back to disk using a temp-file swap."""
        temp_target = f"{self.target_yaml}.tmp"
        try:
            with open(temp_target, 'w', encoding='utf-8') as f:
                yaml.dump(state_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            
            if os.path.exists(self.target_yaml):
                os.remove(self.target_yaml)
            os.rename(temp_target, self.target_yaml)
            return True
        except Exception as e:
            print(f"[-] Write failure during atomic swap: {e}", file=sys.stderr)
            if os.path.exists(temp_target):
                try:
                    os.remove(temp_target)
                except:
                    pass
            return False
