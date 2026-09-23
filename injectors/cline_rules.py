#!/usr/bin/env python3
"""
Antigravity Injector Module: Cline Rules Target Injector
Author: The Operator & Vespera
Description: Dynamically injects assembled persona baseline directives, telemetry, 
             and workspace rules into .clinerules files.
"""

import sys
from pathlib import Path
from core.assembler import DynamicPromptAssembler
from injectors.base import BaseInjector

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"

class ClineRulesInjector(BaseInjector):
    def __init__(self, workspace_root=None, db_path=None):
        super().__init__()
        self.workspace_root = Path(workspace_root or PROJECT_ROOT)
        self.db_path = Path(db_path or DB_PATH)
        self.assembler = DynamicPromptAssembler(workspace_root=self.workspace_root)
        self.output_file = self.workspace_root / ".clinerules"

    def inject(self, db=None, dry_run=False, project_tag=None) -> bool:
        """Assembles the compact persona payload and writes it to .clinerules."""
        # Defensive handling if called as inject(project_tag) with string
        if isinstance(db, str) and project_tag is None:
            project_tag = db
            db = None
        print(f"[*] Injecting dynamic persona into {self.output_file.name}...")
        try:
            # Fetch compact prompt specifically structured for IDE rules
            content = self.assembler.assemble_compact_prompt(project_tag=project_tag, top_n=5)
            if dry_run:
                print(f"[DRY RUN] Would write to {self.output_file}")
                return True
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write(content)
                
            print(f"[+] Successfully synced: {self.output_file}")
            return True
        except Exception as e:
            print(f"[-] Error injecting into {self.output_file.name}: {e}")
            return False

if __name__ == "__main__":
    injector = ClineRulesInjector()
    success = injector.inject()
    sys.exit(0 if success else 1)