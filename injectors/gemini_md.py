#!/usr/bin/env python3
"""
Antigravity Overdrive :: Gemini MD Injector
Injects master persona identity and memory structures into the SINGLE SOVEREIGN
master protocol file: ~/.gemini/GEMINI.md (Global machine-wide user rule).

Actively purges duplicate/stale GEMINI.md and AGENTS.md files across workspace
directories to prevent duplicate rule loading and context token bloat.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.assembler import DynamicPromptAssembler
from injectors.base import BaseInjector
from injectors.google_docs import GoogleDocsInjector


class GeminiMdInjector(BaseInjector):
    def __init__(self, llm_model=None, vector_model=None, workspace_root: Path = None):
        super().__init__()
        self.workspace_root = Path(workspace_root) if workspace_root else PROJECT_ROOT
        
        # The SINGLE Sovereign Master Protocol Target:
        # ~/.gemini/GEMINI.md is automatically discovered by Antigravity as the global user rule (user_global).
        # Writing to multiple project or parent directories duplicates the 22KB protocol into the context window.
        home_dir = Path.home()
        self.master_protocol_file = home_dir / ".gemini" / "GEMINI.md"
        self.target_files = [self.master_protocol_file]
        
        # Obsolete duplicate files that must be purged to prevent multi-rule loading in Antigravity UI
        self.duplicate_files_to_purge = [
            home_dir / ".gemini" / "config" / "AGENTS.md",
            Path(r"D:\AI\GEMINI.md"),
            Path(r"D:\AI\Projects\GEMINI.md"),
            self.workspace_root / "GEMINI.md",
            Path(r"D:\AI\Projects\ComfyUI\GEMINI.md"),
            Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\GEMINI.md"),
        ]

        self.assembler = DynamicPromptAssembler(workspace_root=self.workspace_root)

    def purge_duplicates(self) -> int:
        """Purges obsolete duplicate GEMINI.md and AGENTS.md files across workspaces."""
        purged = 0
        for dup in self.duplicate_files_to_purge:
            try:
                if dup.exists() and dup.resolve() != self.master_protocol_file.resolve():
                    dup.unlink()
                    print(f"[*] Purged duplicate protocol file: {dup}")
                    purged += 1
            except Exception as e:
                print(f"[-] Could not purge {dup}: {e}")
        return purged

    def inject(self, db=None, dry_run=False, project_tag=None) -> bool:
        """Generates the master persona payload and syncs it to the single master target."""
        header_banner = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n" + "=" * 80 + "\n"
        
        if db is not None:
            updated_content = f"{header_banner}" + GoogleDocsInjector().compile_google_docs_payload(db)
        else:
            payload = self.assembler.build_identity_header()
            updated_content = f"{header_banner}{payload}"

        if dry_run:
            print(f"[DRY RUN] Would write single master protocol to: {self.master_protocol_file}")
            return True

        # 1. Clean up duplicate ghost rule files across disk
        self.purge_duplicates()

        # 2. Inject into the single sovereign master file
        try:
            self.master_protocol_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.master_protocol_file, "w", encoding="utf-8") as f:
                f.write(updated_content)
                
            print(f"[+] Successfully synced single master protocol: {self.master_protocol_file}")
            return True
        except Exception as e:
            print(f"[-] Failed to sync master protocol to {self.master_protocol_file}: {e}")
            return False


if __name__ == "__main__":
    injector = GeminiMdInjector()
    injector.inject()