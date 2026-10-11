#!/usr/bin/env python3
r"""
Antigravity Overdrive :: Gemini MD Injector
Injects master persona identity and memory structures into the SINGLE SOVEREIGN
master protocol file: D:\AI\GEMINI.md (Global user rule  -  discovered by Antigravity).

Actively purges duplicate/stale GEMINI.md and AGENTS.md files across workspace
directories to prevent duplicate rule loading and context token bloat.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.assembler import DynamicPromptAssembler
from core.utils import atomic_write
from injectors.base import BaseInjector


class GeminiMdInjector(BaseInjector):
    def __init__(self, llm_model=None, vector_model=None, workspace_root: Path = None):
        super().__init__()
        self.workspace_root = Path(workspace_root) if workspace_root else PROJECT_ROOT

        # The SINGLE Sovereign Master Protocol Target:
        # D:\AI\GEMINI.md is automatically discovered by Antigravity as the global user rule (user_global).
        # Resolve master protocol target dynamically: check environment override first,
        # fallback to D:\AI\GEMINI.md if present, otherwise write to workspace root.
        custom_protocol = os.environ.get("ULM_MASTER_PROTOCOL")
        if custom_protocol:
            self.master_protocol_file = Path(custom_protocol)
        elif Path(r"D:\AI").exists():
            self.master_protocol_file = Path(r"D:\AI\GEMINI.md")
        else:
            self.master_protocol_file = self.workspace_root / "GEMINI.md"
        self.target_files = [self.master_protocol_file]

        home_dir = Path.home()
        # Obsolete duplicate files across workspace sub-projects.
        # Global user configuration rules (~/.gemini/config/AGENTS.md) are protected from deletion.
        self.duplicate_files_to_purge = [
            Path(r"D:\AI\Projects\GEMINI.md"),
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

        # Always use the lean assembled identity header to preserve the <5KB protocol size
        payload = self.assembler.build_identity_header(purge_mirrors=True)
        updated_content = f"{header_banner}{payload}"

        if dry_run:
            print(f"[DRY RUN] Would write single master protocol to: {self.master_protocol_file}")
            return True

        # 1. Clean up duplicate ghost rule files across disk
        self.purge_duplicates()

        # 2. Inject into the single sovereign master file atomically
        try:
            atomic_write(self.master_protocol_file, updated_content)
            print(f"[+] Successfully synced single master protocol: {self.master_protocol_file}")
            return True
        except Exception as e:
            print(f"[-] Failed to sync master protocol to {self.master_protocol_file}: {e}")
            return False


if __name__ == "__main__":
    injector = GeminiMdInjector()
    injector.inject()