import os
import sys
import yaml
from pathlib import Path
from datetime import datetime
from injectors.base import BaseInjector

class GeminiMdInjector(BaseInjector):
    """Atomically writes high-density memory summaries to chatlog.yaml and ensures GEMINI.md has a valid pointer."""
    
    TECH_KEYWORDS = ["ETL", "STREAM", "ATOMIC", "MEMORY", "PORTABLE", "STABLE DIFFUSION", "COMFYUI", "FLUX", "LORA", "GIT", "SCHEDULER", "O(1)"]
    
    def __init__(self, target_file=None):
        if not target_file:
            # Dynamically resolve GEMINI.md location for cross-platform compatibility
            possible_paths = [
                Path(r"D:\GEMINI.md"),
                Path(os.path.expanduser("~")) / "GEMINI.md",
                Path(__file__).resolve().parents[2] / "GEMINI.md"
            ]
            for p in possible_paths:
                if p.exists():
                    target_file = str(p)
                    break
            if not target_file:
                # Fallback to standard location
                target_file = str(possible_paths[0])
                
        super().__init__(target_file)
        
    def generate_gemini_summary(self, logs):
        """Zero-dependency HTTP REST call to Gemini API for high-fidelity technical summarization."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            try:
                env_path = Path(__file__).resolve().parents[1] / ".env"
                if env_path.exists():
                    with open(env_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip() and not line.startswith("#"):
                                parts = line.split("=", 1)
                                if len(parts) == 2 and parts[0].strip() == "GEMINI_API_KEY":
                                    api_key = parts[1].strip().strip('"').strip("'")
                                    break
            except:
                pass
                
        if not api_key:
            return None
            
        formatted_dialogue = []
        for msg in logs:
            formatted_dialogue.append(f"{msg.get('sender')}: {msg.get('text')}")
        full_transcript = "\n".join(formatted_dialogue)
        
        if len(full_transcript) > 50000:
            full_transcript = full_transcript[-50000:]
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
        prompt = (
            "You are a technical archivist. Analyze the following chat log between a developer (Pilot) and an AI companion (Vespera). "
            "Compile a highly dense, 1-2 sentence technical summary of the key achievements, solved issues, and active technical stack. "
            "Be extremely specific about errors fixed, files modified, or features implemented. Avoid any conversational fluff, "
            "meta-commentary, or politeness. Ground your response completely in the facts of the transcript."
        )
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": f"{prompt}\n\nChat Log:\n{full_transcript}"}
                ]
            }]
        }
        
        import urllib.request
        import json
        import urllib.error
        import time
        
        max_retries = 3
        backoff = 4.0
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=90) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    raw_text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
                    return raw_text.replace("\n", " ").strip()
            except urllib.error.HTTPError as he:
                if he.code == 429:
                    if attempt < max_retries - 1:
                        print(f"[!] Gemini API rate limited (429). Retrying in {backoff} seconds...")
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                print(f"[-] Gemini API HTTP Error {he.code}: {he.reason}", file=sys.stderr)
                return None
            except Exception as e:
                print(f"[-] Gemini API summarization failed: {e}", file=sys.stderr)
                return None
        return None


    def compile_summaries_to_dict(self, db):
        """Compiles technical summaries and structures them into a list of dictionaries for YAML serialization."""
        self.state_mutated = False
        
        import sqlite3
        compiled_sessions = []
        try:
            with sqlite3.connect(db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT session_id, updated_at, summary FROM sessions ORDER BY updated_at DESC")
                sessions = [dict(r) for r in c.fetchall()]
                
                for session in sessions:
                    session_id = session["session_id"]
                    updated_at = session["updated_at"]
                    summary = session["summary"]
                    
                    c.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
                    msgs = [dict(r) for r in c.fetchall()]
                    
                    try:
                        parsed_date = datetime.fromisoformat(updated_at.split(".")[0])
                        formatted_date = parsed_date.strftime("%b %d, %Y at %I:%M %p")
                    except:
                        formatted_date = updated_at
                    
                    detected_tech = set()
                    for turn in msgs:
                        text = turn.get("content", "").upper()
                        for kw in self.TECH_KEYWORDS:
                            if kw in text:
                                detected_tech.add(kw)
                    
                    turns_count = len(msgs)
                    if not summary:
                        print(f"[*] Compiling dynamic Gemini memory summary for chat {session_id[:8]}...")
                        logs_param = [{"sender": m["role"], "text": m["content"]} for m in msgs]
                        summary = self.generate_gemini_summary(logs_param)
                        if summary:
                            c.execute("UPDATE sessions SET summary = ? WHERE session_id = ?", (summary, session_id))
                            self.state_mutated = True
                        else:
                            last_turn = ""
                            if msgs:
                                last_msg = msgs[-1]
                                last_turn = f"{last_msg.get('role')}: {last_msg.get('content')[:120]}..."
                            summary = last_turn
                        
                        import time
                        time.sleep(2.0)
                    
                    compiled_sessions.append({
                        "id": session_id[:8],
                        "date": formatted_date,
                        "tech_stack": list(detected_tech) if detected_tech else ["General Dialogue"],
                        "turns": turns_count,
                        "summary": summary
                    })
                if self.state_mutated:
                    conn.commit()
        except sqlite3.Error as e:
            print(f"[-] SQLite compilation error in GeminiMdInjector: {e}")
            
        return compiled_sessions

    def inject(self, db, dry_run=False):
        """Atomic write to chatlog.yaml and ensures pointer validation in target_file."""
        target_path = Path(self.target_file)
        if not target_path.exists():
            print(f"[-] Target protocol file not found at {self.target_file}.")
            return False
            
        target_dir = target_path.parent
        yaml_file = target_dir / "chatlog.yaml"
        
        import sqlite3
        total_chats = 0
        try:
            with sqlite3.connect(db.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM sessions")
                total_chats = c.fetchone()[0]
        except sqlite3.Error:
            pass
            
        now_iso = datetime.now().isoformat()
        compiled_dict = self.compile_summaries_to_dict(db)
        
        yaml_payload = {
            "metadata": {
                "total_indexed_sessions": total_chats,
                "last_memory_sync": now_iso
            },
            "sessions": compiled_dict
        }
        
        if dry_run:
            print("\n[+] --- DRY RUN INJECTION PAYLOAD (chatlog.yaml) ---")
            print(yaml.dump(yaml_payload, sort_keys=False, default_flow_style=False, allow_unicode=True))
            print("[+] --- END DRY RUN PAYLOAD ---")
            return True
            
        try:
            # 1. Write the dynamic memory to chatlog.yaml atomically
            temp_yaml = yaml_file.with_suffix(".yaml.tmp")
            with open(temp_yaml, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_payload, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
            if yaml_file.exists():
                os.remove(yaml_file)
            os.rename(temp_yaml, yaml_file)
            print(f"[+] Dynamic memory ledger successfully written to {yaml_file}")
            
            # 2. Check and enforce system memory pointer in GEMINI.md
            with open(target_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tag_start = "<SystemMemory>"
            tag_end = "</SystemMemory>"
            
            pointer_payload = (
                f"================================================================================\n"
                f"<SystemMemory>\n"
                f"  <!-- DYNAMIC SYSTEM MEMORY ANCHOR - DO NOT MANUAL EDIT -->\n"
                f"  System Memory Ledger is maintained dynamically in:\n"
                f"  [chatlog.yaml](file:///{yaml_file.as_posix()}) (created in the same directory as this protocol file).\n\n"
                f"  INSTRUCTIONS:\n"
                f"  At the beginning of every session, you MUST read the last 2-3 chat session entries in chatlog.yaml to retrieve the context of the previous conversations.\n"
                f"</SystemMemory>\n"
            )
            
            if tag_start in content and tag_end in content:
                before_part = content.split("================================================================================\n" + tag_start)[0]
                if len(before_part) == len(content):
                    before_part = content.split(tag_start)[0]
                after_part = content.split(tag_end)[1]
                after_part = after_part.replace("================================================================================\n", "", 1)
                
                new_content = before_part.rstrip() + "\n\n" + pointer_payload.rstrip() + "\n" + after_part.lstrip()
            else:
                new_content = content.rstrip() + "\n\n" + pointer_payload
                
            if new_content != content:
                backup_file = target_path.with_suffix(".bak")
                if backup_file.exists():
                    os.remove(backup_file)
                os.rename(target_path, backup_file)
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"[+] Verified and updated master protocol pointer in {target_path}")
            else:
                print(f"[*] Master protocol pointer is already up-to-date in {target_path}")
                
            return True
            
        except Exception as e:
            print(f"[-] Mutation failure: {e}", file=sys.stderr)
            return False

