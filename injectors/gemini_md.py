import os
import sys
from datetime import datetime
from injectors.base import BaseInjector

class GeminiMdInjector(BaseInjector):
    """Atomically injects high-density markdown memory into protocol files (like D:\\GEMINI.md)."""
    
    TECH_KEYWORDS = ["ETL", "STREAM", "ATOMIC", "MEMORY", "PORTABLE", "STABLE DIFFUSION", "COMFYUI", "FLUX", "LORA", "GIT", "SCHEDULER", "O(1)"]
    
    def __init__(self, target_file=None):
        if not target_file:
            target_file = r"D:\GEMINI.md"
        super().__init__(target_file)
        
    def generate_gemini_summary(self, logs):
        """Zero-dependency HTTP REST call to Gemini API for high-fidelity technical summarization."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            # Fallback: attempt to load from a local git-ignored .env file
            try:
                env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
                if os.path.exists(env_path):
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
        
        # Crop context payload if it exceeds 50,000 characters to protect rate limits
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
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                raw_text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
                return raw_text.replace("\n", " ").strip()
        except Exception as e:
            print(f"[-] Gemini API summarization failed: {e}", file=sys.stderr)
            return None

    def compile_summaries(self, sync_data):
        """Compiles highly dense technical summaries of each chat session using Gemini API or cached states."""
        summaries = []
        chats = sync_data.get("chats", {})
        self.state_mutated = False
        
        # Sort chats chronologically: newest first
        sorted_chats = sorted(
            chats.items(),
            key=lambda x: x[1].get("last_mutated", ""),
            reverse=True
        )
        
        for c_id, chat_info in sorted_chats:
            logs = chat_info.get("log", [])
            last_mutated = chat_info.get("last_mutated", "Unknown")
            
            try:
                parsed_date = datetime.fromisoformat(last_mutated.split(".")[0])
                formatted_date = parsed_date.strftime("%b %d, %Y at %I:%M %p")
            except:
                formatted_date = last_mutated
            
            # Identify active technologies
            detected_tech = set()
            for turn in logs:
                text = turn.get("text", "").upper()
                for kw in self.TECH_KEYWORDS:
                    if kw in text:
                        detected_tech.add(kw)
            
            tech_list = ", ".join(detected_tech) if detected_tech else "General Dialogue"
            turns_count = len(logs)
            
            # Retrieve or generate summary
            summary = chat_info.get("summary")
            if not summary:
                print(f"[*] Compiling dynamic Gemini memory summary for chat {c_id[:8]}...")
                summary = self.generate_gemini_summary(logs)
                if summary:
                    chat_info["summary"] = summary
                    self.state_mutated = True
                else:
                    # Fallback to heuristic last action
                    last_turn = ""
                    if logs:
                        last_msg = logs[-1]
                        last_turn = f"{last_msg.get('sender')}: {last_msg.get('text')[:120]}..."
                    summary = last_turn
                
                # Sleep briefly to respect Gemini Free Tier 15 RPM (Requests Per Minute) limits
                import time
                time.sleep(2.0)
            
            summaries.append(
                f"  - **Chat Thread {c_id[:8]}** ({formatted_date}):\n"
                f"    * Tech Stack: `{tech_list}`\n"
                f"    * Interaction Turns: {turns_count}\n"
                f"    * Summary: {summary}\n"
            )
            
        return "\n".join(summaries)
        
    def inject(self, sync_data, dry_run=False):
        """Atomic tag splicing and backup rotation injection."""
        if not os.path.exists(self.target_file):
            print(f"[-] Target protocol file not found at {self.target_file}.")
            return False
            
        metadata = sync_data.get("metadata", {})
        total_chats = metadata.get("total_chats", 0)
        now_iso = datetime.now().isoformat()
        
        summaries = self.compile_summaries(sync_data)
        payload = (
            "================================================================================\n"
            "<SystemMemory>\n"
            "  <!-- DYNAMIC SYSTEM MEMORY ANCHOR - DO NOT MANUAL EDIT -->\n"
            f"  Total Indexed Sessions: {total_chats}\n"
            f"  Last Memory Sync: {now_iso}\n\n"
            f"{summaries}\n"
            "</SystemMemory>\n"
        )
        
        try:
            with open(self.target_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tag_start = "<SystemMemory>"
            tag_end = "</SystemMemory>"
            
            if tag_start in content and tag_end in content:
                before_part = content.split("================================================================================\n" + tag_start)[0]
                if len(before_part) == len(content):
                    before_part = content.split(tag_start)[0]
                
                after_part = content.split(tag_end)[1]
                after_part = after_part.replace("================================================================================\n", "", 1)
                
                new_content = before_part.rstrip() + "\n\n" + payload.rstrip() + "\n" + after_part.lstrip()
            else:
                new_content = content.rstrip() + "\n\n" + payload
                
            if dry_run:
                print("\n[+] --- DRY RUN INJECTION PAYLOAD (GEMINI.md) ---")
                print(payload)
                print("[+] --- END DRY RUN PAYLOAD ---")
                return True
                
            # Execute Backup Rotation
            backup_file = f"{self.target_file}.bak"
            if os.path.exists(backup_file):
                os.remove(backup_file)
            os.rename(self.target_file, backup_file)
            
            # Atomic Write
            with open(self.target_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
            print(f"[+] Dynamic memory injection successful. {self.target_file} updated.")
            
            # Commit lazy-compiled summaries back to YAML database to avoid repeated API hits
            if getattr(self, "state_mutated", False) and not dry_run:
                from core.engine import ULMEngine
                engine = ULMEngine()
                engine.commit_atomic_write(sync_data)
                print("[+] Saved lazy-compiled summaries back to master state database.")
                
            return True
        except Exception as e:
            print(f"[-] Mutation failure on {self.target_file}: {e}", file=sys.stderr)
            return False
