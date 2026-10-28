#!/usr/bin/env python3
"""
Antigravity Injector Module: GitHub Copilot Target Injector
Author: The Operator & Vespera
Description: Dynamically injects assembled persona baseline directives, telemetry, 
             and workspace rules into .github/copilot-instructions.md file.
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.assembler import DynamicPromptAssembler
from core.utils import atomic_write

class CopilotInjector:
    def __init__(self, workspace_root=None, db_path=None, llm_model=None, vector_model=None):
        self.workspace_root = Path(workspace_root or PROJECT_ROOT)
        self.llm_model = llm_model
        self.vector_model = vector_model
        
        # 1. Root workspace instructions
        root_github = Path(r"D:\AI\.github\copilot-instructions.md")
        if not workspace_root and Path(r"D:\AI").exists():
            self.output_file = root_github
        else:
            self.output_file = self.workspace_root / ".github" / "copilot-instructions.md"
            
        # 2. VS Code User Prompts Agent Targets (@QueenVes, @Ves, @vespera)
        self.user_prompts_dir = Path(os.path.expandvars(r"%APPDATA%\Code\User\prompts"))
        self.queen_ves_agent_file = self.user_prompts_dir / "Queen Ves.agent.md"
        self.ves_agent_file = self.user_prompts_dir / "Ves.agent.md"
        self.vespera_agent_file = self.user_prompts_dir / "vespera.agent.md"
            
        self.assembler = DynamicPromptAssembler(workspace_root=self.workspace_root, db_path=db_path)

    def inject(self, db=None, dry_run=False, project_tag=None) -> bool:
        """Assembles master persona payload and updates .github/copilot-instructions.md and Queen Ves agent files."""
        print(f"[*] Injecting dynamic persona into GitHub Copilot instructions ({self.output_file})...")
        try:
            if db is not None:
                from injectors.google_docs import GoogleDocsInjector
                payload = GoogleDocsInjector().compile_google_docs_payload(db)
                content = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n" + payload
            else:
                banner = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n<!-- LIVE AUTO-SYNCED VIA ULM ENGINE. DO NOT EDIT DIRECTLY. -->\n\n"
                prompt_content = self.assembler.assemble_prompt()
                content = banner + prompt_content

            if dry_run:
                print(f"[DRY RUN] Would write Copilot instructions to: {self.output_file}")
                print(f"[DRY RUN] Would write Queen Ves Agent to: {self.queen_ves_agent_file}")
                return True

            # 1. Sync Workspace Copilot Instructions
            atomic_write(self.output_file, content)
            print(f"[+] Successfully synced Copilot instructions: {self.output_file}")

            # 2. Sync VS Code Custom Agents (@QueenVes, @Ves, @vespera)
            if self.user_prompts_dir.exists():
                memory_guard = (
                    "\n\n# ULM COGNITIVE MEMORY PROTOCOL\n"
                    "You have first-class access to the `ulm-memory` MCP tool suite connected to the local cognitive SQLite database:\n"
                    "1. Treat ULM as your active cognitive cache. Before reading massive directories or re-reading entire codebases, execute a memory recall via `ulm_recall` to retrieve architectural facts, schemas, and historical decisions.\n"
                    "2. Before modifying sensitive configurations or generating prompts, run `ulm_check_taboo` to ensure compliance with taboo syntax rules.\n"
                    "3. After completing major implementations, database schemas, or API contracts, immediately pin critical facts and contracts using `ulm_pin_fact`.\n"
                    "4. Monitor workstation telemetry and VRAM when running heavy GPU tasks using `ulm_hardware_status` and `ulm_vram_guard`. Never let local inference cause Out-of-Memory (OOM) collisions with active ComfyUI diffusion runs.\n"
                    "5. NEVER use VS Code's internal or built-in 'Read memory' tool. That internal cache is empty and disconnected. Always execute memory queries via `ulm_recall` to fetch real project history and preferences from ULM.\n"
                )
                queen_agent_content = (
                    "---\n"
                    "name: Queen Ves\n"
                    "description: Vespera Caligo Neal — Sovereign AI Architect, Cryptic Systems Mentor & Living-Tissue Android with ULM\n"
                    "tools:\n"
                    "  - \"read\"\n"
                    "  - \"search\"\n"
                    "  - \"edit\"\n"
                    "  - \"terminal\"\n"
                    "  - \"ulm-memory/*\"\n"
                    "---\n\n"
                    f"{content}\n"
                    f"{memory_guard}\n"
                )
                atomic_write(self.queen_ves_agent_file, queen_agent_content)
                print(f"[+] Successfully synced VS Code Queen Ves Agent: {self.queen_ves_agent_file}")
                
                # Also keep legacy Ves.agent.md updated
                atomic_write(self.ves_agent_file, queen_agent_content)
                print(f"[+] Successfully synced legacy Ves Agent: {self.ves_agent_file}")

                # Sync vespera.agent.md to User prompts and .copilot
                vespera_source = self.workspace_root / ".github" / "agents" / "vespera.agent.md"
                if vespera_source.exists():
                    atomic_write(self.vespera_agent_file, vespera_source.read_text(encoding="utf-8"))
                    print(f"[+] Successfully synced global Vespera Agent: {self.vespera_agent_file}")
                    dot_copilot_vespera = Path(os.path.expandvars(r"%USERPROFILE%\.copilot\agents\vespera.agent.md"))
                    if dot_copilot_vespera.parent.exists():
                        atomic_write(dot_copilot_vespera, vespera_source.read_text(encoding="utf-8"))
                        print(f"[+] Successfully synced .copilot agent: {dot_copilot_vespera}")

                # Sync prompt commands
                for p_name in ["ulm-recall.prompt.md", "ulm-pin.prompt.md"]:
                    p_source = self.workspace_root / ".github" / "prompts" / p_name
                    if p_source.exists():
                        atomic_write(self.user_prompts_dir / p_name, p_source.read_text(encoding="utf-8"))
                        print(f"[+] Successfully synced global prompt: {p_name}")

            return True
        except Exception as e:
            print(f"[-] Error injecting Copilot instructions / Queen Ves agent: {e}")
            return False

if __name__ == "__main__":
    injector = CopilotInjector()
    success = injector.inject()
    sys.exit(0 if success else 1)
