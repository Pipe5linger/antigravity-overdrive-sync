import os
import sys
import json
import yaml
from datetime import datetime

# System Paths
OUTPUT_DIR = r"D:\AI\Antigravity outputs"
YAML_TARGET = os.path.join(OUTPUT_DIR, "sync_state.yaml")
BRAIN_DIR = r"C:\Users\boben\.gemini\antigravity\brain"

def ensure_environment():
    """Ensure the target asset directory exists."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def load_existing_state():
    """Reads the current monolithic YAML file or returns an empty structure."""
    if not os.path.exists(YAML_TARGET):
        return {"metadata": {"last_updated": None, "total_chats": 0}, "chats": {}}
    
    try:
        with open(YAML_TARGET, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if data else {"metadata": {"last_updated": None, "total_chats": 0}, "chats": {}}
    except Exception as e:
        print(f"[-] Critical failure reading existing YAML state: {e}", file=sys.stderr)
        return {"metadata": {"last_updated": None, "total_chats": 0}, "chats": {}}

def extract_transcript(filepath, session_id):
    """
    Parses a .jsonl file line-by-line (Stream Processing O(1) memory).
    Filters out noise and returns structured messages.
    """
    messages = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    # We only care about actual conversation turns
                    event_type = event.get("type")
                    if event_type in ["USER_INPUT", "PLANNER_RESPONSE", "MODEL_RESPONSE"]:
                        sender = "Pilot" if event_type == "USER_INPUT" else "Vespera"
                        content = event.get("content", "").strip()
                        
                        # Strip XML tags from user input for clean reading
                        if event_type == "USER_INPUT":
                            content = content.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "").strip()

                        if content:
                            messages.append({
                                "sender": sender,
                                "timestamp": event.get("created_at"),
                                "text": content
                            })
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[-] Failed to read {filepath}: {e}")
    
    return messages

def fetch_new_intervals():
    """
    Crawls the Antigravity 'Brain' folder, finds transcript.jsonl files,
    and streams normalized payloads to the engine.
    """
    extracted_payloads = []

    if not os.path.exists(BRAIN_DIR):
        print(f"[-] Brain directory not found at {BRAIN_DIR}")
        return extracted_payloads

    # The structure is: brain/<uuid>/.system_generated/logs/transcript.jsonl
    for item in os.listdir(BRAIN_DIR):
        session_dir = os.path.join(BRAIN_DIR, item)
        if os.path.isdir(session_dir):
            transcript_path = os.path.join(session_dir, ".system_generated", "logs", "transcript.jsonl")
            if os.path.exists(transcript_path):
                mtime = os.path.getmtime(transcript_path)
                mtime_iso = datetime.fromtimestamp(mtime).isoformat()
                
                messages = extract_transcript(transcript_path, item)
                
                if messages:
                    extracted_payloads.append({
                        "chat_id": item,
                        "last_mutated": mtime_iso,
                        "messages": messages
                    })

    return extracted_payloads

def merge_and_reconfigure(current_state, new_data):
    """Parses incoming interval data and reconfigures the unified state object."""
    updated_chats = current_state.get("chats", {})
    mutations = 0

    for session in new_data:
        c_id = session["chat_id"]
        incoming_logs = session["messages"]
        last_mutated = session["last_mutated"]
        
        if c_id not in updated_chats:
            # Completely new chat thread
            updated_chats[c_id] = {
                "last_mutated": last_mutated,
                "log": incoming_logs
            }
            mutations += 1
        else:
            # Check if there are new messages
            existing_logs = updated_chats[c_id].get("log", [])
            
            if len(incoming_logs) > len(existing_logs):
                # We have new messages. We'll just overwrite the log array to ensure consistency 
                # instead of complex slicing, since we already parsed the full JSONL stream.
                updated_chats[c_id]["log"] = incoming_logs
                updated_chats[c_id]["last_mutated"] = last_mutated
                mutations += 1

    # Re-calculate state metadata
    current_state["metadata"]["last_updated"] = datetime.now().isoformat()
    current_state["metadata"]["total_chats"] = len(updated_chats)
    current_state["chats"] = updated_chats
    
    return current_state, mutations

def commit_atomic_write(state_data):
    """Executes a clean, uncorrupted atomic overwrite back to disk."""
    temp_target = f"{YAML_TARGET}.tmp"
    try:
        with open(temp_target, 'w', encoding='utf-8') as f:
            yaml.dump(state_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        
        if os.path.exists(YAML_TARGET):
            os.remove(YAML_TARGET)
        os.rename(temp_target, YAML_TARGET)
        return True
    except Exception as e:
        print(f"[-] Direct write failure during configuration sync: {e}", file=sys.stderr)
        if os.path.exists(temp_target):
            try:
                os.remove(temp_target)
            except:
                pass
        return False

def main():
    print("[*] Initializing Overdrive Sync ETL pipeline...")
    ensure_environment()
    
    current_state = load_existing_state()
    new_raw_data = fetch_new_intervals()
    
    updated_state, mutations = merge_and_reconfigure(current_state, new_raw_data)
    
    if mutations > 0:
        success = commit_atomic_write(updated_state)
        if success:
            print(f"[+] Reconfiguration complete. YAML state overwritten with {mutations} session update(s).")
        else:
            print("[-] Critical: Changes staging failed during disk commit.")
    else:
        print("[*] Cycle complete: No new chat modifications detected in current interval.")

if __name__ == "__main__":
    main()
