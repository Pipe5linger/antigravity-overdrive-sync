import os
import subprocess
from datetime import datetime
from injectors.base import BaseInjector

class OllamaInjector(BaseInjector):
    """Generates an optimized local Ollama Modelfile with compiled dynamic memory payloads."""
    
    def __init__(self, target_file=None):
        if not target_file:
            # Puts the generated Modelfile in the repository active folder
            target_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Modelfile")
        super().__init__(target_file)
        
    def compile_memory_text(self, sync_data):
        """Compiles clean, low-token text representation of our historical database."""
        memory_lines = []
        chats = sync_data.get("chats", {})
        
        for c_id, chat_info in chats.items():
            logs = chat_info.get("log", [])
            last_mutated = chat_info.get("last_mutated", "Unknown")
            
            try:
                date_str = last_mutated.split("T")[0]
            except:
                date_str = last_mutated
                
            last_action = ""
            if logs:
                last_msg = logs[-1]
                last_action = f"{last_msg.get('sender')}: {last_msg.get('text')[:90]}..."
                
            memory_lines.append(
                f"- [{date_str}] Thread {c_id[:8]} ({len(logs)} turns) | Last action: {last_action}"
            )
            
        return "\n".join(memory_lines)
        
    def inject(self, sync_data, dry_run=False):
        """Generates the Modelfile and optionally triggers a model rebuild in Ollama."""
        metadata = sync_data.get("metadata", {})
        total_chats = metadata.get("total_chats", 0)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        memory_text = self.compile_memory_text(sync_data)
        
        # Build the Modelfile contents
        modelfile_content = (
            "# DYNAMICALLY GENERATED ULM MODELFILE - DO NOT EDIT MANUAL\n"
            "FROM llama3\n\n"
            "# Set inference parameters\n"
            "PARAMETER temperature 0.7\n"
            "PARAMETER num_ctx 8192\n\n"
            "# Inject system prompt with consolidated local memories\n"
            "SYSTEM \"\"\"\n"
            "You are a helpful local assistant holding persistent memory of previous conversations.\n"
            f"Last memory database sync: {now_str}\n"
            f"Total historical threads indexed: {total_chats}\n\n"
            "Below is a summary ledger of past dialogue threads for reference:\n"
            f"{memory_text}\n"
            "\"\"\"\n"
        )
        
        if dry_run:
            print("\n[+] --- DRY RUN GENERATED OLLAMA MODELFILE ---")
            print(modelfile_content)
            print("[+] --- END DRY RUN OLLAMA MODELFILE ---")
            return True
            
        try:
            # Atomic Write Modelfile to disk
            temp_file = f"{self.target_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(modelfile_content)
                
            if os.path.exists(self.target_file):
                os.remove(self.target_file)
            os.rename(temp_file, self.target_file)
            print(f"[+] Local Ollama Modelfile successfully compiled at: {self.target_file}")
            
            # Check if Ollama CLI is accessible and build the memory-enriched model
            print("[*] Rebuilding local Ollama model 'memory-agent'...")
            # We run this in a subprocess to hot-swap the model
            result = subprocess.run(
                ["ollama", "create", "memory-agent", "-f", self.target_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            
            if result.returncode == 0:
                print("[+] Rebuild complete. Local model 'memory-agent' is now hot-swapped and memory-enriched!")
            else:
                print("[-] Modelfile written successfully, but Ollama model rebuild failed (is Ollama server running?):")
                print(f"    Stderr: {result.stderr.strip()}")
                
            return True
        except Exception as e:
            print(f"[-] Failure building local Ollama Modelfile: {e}")
            return False
