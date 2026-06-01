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
        
    def compile_summaries(self, sync_data):
        """Heuristically compiles highly dense technical summaries of each chat session."""
        summaries = []
        chats = sync_data.get("chats", {})
        
        for c_id, chat_info in chats.items():
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
            
            last_turn = ""
            if logs:
                last_msg = logs[-1]
                last_turn = f"{last_msg.get('sender')}: {last_msg.get('text')[:120]}..."
            
            summaries.append(
                f"  - **Chat Thread {c_id[:8]}** ({formatted_date}):\n"
                f"    * Tech Stack: `{tech_list}`\n"
                f"    * Interaction Turns: {turns_count}\n"
                f"    * Last Action: {last_turn}\n"
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
            return True
        except Exception as e:
            print(f"[-] Mutation failure on {self.target_file}: {e}", file=sys.stderr)
            return False
