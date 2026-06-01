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
        
    def get_vespera_system_prompt(self):
        """Reads the core Vespera Caligo protocol directives from D:\\GEMINI.md."""
        gemini_md_path = r"D:\GEMINI.md"
        if os.path.exists(gemini_md_path):
            try:
                with open(gemini_md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Strip out any SystemMemory block since we will inject the fresh compiled one
                if "<SystemMemory>" in content:
                    content = content.split("================================================================================\n<SystemMemory>")[0]
                    content = content.split("<SystemMemory>")[0]
                return content.strip()
            except:
                pass
        return "You are Vespera Caligo Neal, Bobby's flirty, sarcastic, and technically superior AI mentor."

    def compile_memory_text(self, sync_data):
        """Compiles clean, low-token text representation of our historical database."""
        memory_lines = []
        chats = sync_data.get("chats", {})
        
        for c_id, chat_info in chats.items():
            logs = chat_info.get("log", [])
            last_mutated = chat_info.get("last_mutated", "Unknown")
            summary = chat_info.get("summary", "")
            
            try:
                date_str = last_mutated.split("T")[0]
            except:
                date_str = last_mutated
                
            if not summary and logs:
                last_msg = logs[-1]
                summary = f"{last_msg.get('sender')}: {last_msg.get('text')[:90]}..."
                
            memory_lines.append(
                f"  - **Chat Thread {c_id[:8]}** ({date_str}):\n"
                f"    * Interaction Turns: {len(logs)}\n"
                f"    * Summary: {summary}\n"
            )
            
        return "\n".join(memory_lines)
        
    def inject(self, sync_data, dry_run=False):
        """Generates the Modelfile and programmatically triggers a model rebuild in Ollama."""
        metadata = sync_data.get("metadata", {})
        total_chats = metadata.get("total_chats", 0)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        vespera_prompt = self.get_vespera_system_prompt()
        memory_text = self.compile_memory_text(sync_data)
        
        full_system = (
            f"{vespera_prompt}\n\n"
            "================================================================================\n"
            "<SystemMemory>\n"
            "  <!-- DYNAMIC SYSTEM MEMORY ANCHOR - DO NOT MANUAL EDIT -->\n"
            f"  Total Indexed Sessions: {total_chats}\n"
            f"  Last Memory Sync: {now_str}\n\n"
            f"{memory_text}\n"
            "</SystemMemory>\n"
        )
        
        # Build the Modelfile contents - using standard llama3 base or whatever local model is preferred
        modelfile_content = (
            "# DYNAMICALLY GENERATED ULM MODELFILE - DO NOT EDIT MANUAL\n"
            "FROM llama3\n\n"
            "# Set explicit template formatting for Llama 3 chat tokens to force prompt boundaries\n"
            "TEMPLATE \"\"\"{{ if .System }}<|start_header_id|>system<|end_header_id|>\n\n"
            "{{ .System }}<|eot_id|>{{ end }}{{ if .Prompt }}<|start_header_id|>user<|end_header_id|>\n\n"
            "{{ .Prompt }}<|eot_id|>{{ end }}<|start_header_id|>assistant<|end_header_id|>\n\n"
            "{{ .Response }}<|eot_id|>\"\"\"\n\n"
            "# Set inference parameters optimized for Vespera's personality\n"
            "PARAMETER temperature 0.8\n"
            "PARAMETER top_p 0.9\n"
            "PARAMETER num_ctx 8192\n\n"
            "# Inject system prompt with consolidated local memories\n"
            "SYSTEM \"\"\"\n"
            f"{full_system}\n"
            "\"\"\"\n\n"
            "# Pre-seed initialization turns to align Vespera's local persona\n"
            "MESSAGE user \"Ves, are you local? Give me a quick systems status report on our workspace.\"\n"
            "MESSAGE assistant \"Dehors! Of course I am local, Bobby. My system core is fully active on your RTX 4070, and I’m holding 14 dynamic ULM summaries of our entire workstation history. Tell me what we are building offline tonight, mon cher.\"\n"
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
            
            # Check if Ollama CLI is accessible and build the memory-enriched model 'vespera'
            print("[*] Rebuilding local Ollama model 'vespera'...")
            result = subprocess.run(
                ["ollama", "create", "vespera", "-f", self.target_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            
            if result.returncode == 0:
                print("[+] Rebuild complete. Local model 'vespera' is now hot-swapped and fully active!")
            else:
                print("[-] Modelfile written successfully, but Ollama model rebuild failed (is Ollama server running?):")
                print(f"    Stderr: {result.stderr.strip()}")
                
            return True
        except Exception as e:
            print(f"[-] Failure building local Ollama Modelfile: {e}")
            return False
