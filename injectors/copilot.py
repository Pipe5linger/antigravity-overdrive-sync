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

class CopilotInjector:
    def __init__(self, workspace_root=None, db_path=None):
        self.workspace_root = Path(workspace_root or PROJECT_ROOT)
        # Default target is root workspace .github/copilot-instructions.md if D:\AI exists
        root_github = Path(r"D:\AI\.github\copilot-instructions.md")
        if not workspace_root and Path(r"D:\AI").exists():
            self.output_file = root_github
        else:
            self.output_file = self.workspace_root / ".github" / "copilot-instructions.md"
            
        self.assembler = DynamicPromptAssembler(workspace_root=self.workspace_root, db_path=db_path)

    def inject(self, db=None, dry_run=False, project_tag=None) -> bool:
        """Assembles master persona payload and updates .github/copilot-instructions.md."""
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
                return True

            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            self.output_file.write_text(content, encoding="utf-8")
            print(f"[+] Successfully synced Copilot instructions: {self.output_file}")
            return True
        except Exception as e:
            print(f"[-] Error injecting into {self.output_file}: {e}")
            return False

if __name__ == "__main__":
    injector = CopilotInjector()
    success = injector.inject()
    sys.exit(0 if success else 1)
