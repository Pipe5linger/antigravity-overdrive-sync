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
        # Resolve master protocol target dynamically:
        # Priority 1: ULM_MASTER_PROTOCOL environment variable override
        # Priority 2: Global Antigravity plugin rule: ~/.gemini/config/plugins/vespera-overdrive/rules/GEMINI.md
        # Priority 3: Global Antigravity user rule: ~/.gemini/GEMINI.md
        # Priority 4: Workspace root fallback: self.workspace_root / "GEMINI.md"
        home_dir = Path.home()
        custom_protocol = os.environ.get("ULM_MASTER_PROTOCOL")
        plugin_rules_target = home_dir / ".gemini" / "config" / "plugins" / "vespera-overdrive" / "rules" / "GEMINI.md"
        global_user_rule = home_dir / ".gemini" / "GEMINI.md"

        if custom_protocol:
            self.master_protocol_file = Path(custom_protocol)
        elif plugin_rules_target.parent.exists():
            self.master_protocol_file = plugin_rules_target
        elif global_user_rule.parent.exists():
            self.master_protocol_file = global_user_rule
        else:
            self.master_protocol_file = self.workspace_root / "GEMINI.md"
        self.target_files = [self.master_protocol_file]

        # Obsolete duplicate files across parent directories and workspace sub-projects.
        # Parent directory rules (like D:\AI\GEMINI.md, D:\AI\Projects\AGENTS.md) cause Antigravity
        # to walk up the tree and inject duplicate rules into every subproject opened under D:\AI!
        # Protected: Global plugin rules, ~/.gemini/config/AGENTS.md, and workspace_root / "AGENTS.md".
        self.duplicate_files_to_purge = [
            Path(r"D:\AI\GEMINI.md"),
            Path(r"D:\AI\AGENTS.md"),
            Path(r"D:\AI\Projects\GEMINI.md"),
            Path(r"D:\AI\Projects\AGENTS.md"),
            Path(r"D:\AI\Projects\ComfyUI\GEMINI.md"),
            Path(r"D:\AI\Projects\ComfyUI\AGENTS.md"),
            Path(r"D:\AI\Projects\ComfyUI\custom_nodes\ComfyUI-Lora-Manager\AGENTS.md"),
            Path(r"D:\AI\Projects\ComfyUI\custom_nodes\comfyui-node-organizer\AGENTS.md"),
            Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\GEMINI.md"),
            Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\AGENTS.md"),
            Path(r"D:\AI\Projects\cline\sdk\AGENTS.md"),
            Path(r"D:\AI\Projects\cline\sdk\packages\llms\AGENTS.md"),
            Path(r"D:\AI\Projects\OneTrainer-master\OneTrainer-master\venv\src\diffusers\AGENTS.md"),
            Path(r"D:\AI\Projects\OneTrainer-master\OneTrainer-master\venv\src\diffusers\.ai\AGENTS.md"),
        ]
        # If the master target is global plugin or user home, purge workspace GEMINI.md duplicate as well
        if self.master_protocol_file.resolve() != (self.workspace_root / "GEMINI.md").resolve():
            self.duplicate_files_to_purge.append(self.workspace_root / "GEMINI.md")
        # Purge root workspace AGENTS.md to avoid duplicate loading in Antigravity (global plugin handles it)
        self.duplicate_files_to_purge.append(self.workspace_root / "AGENTS.md")

        self.assembler = DynamicPromptAssembler(workspace_root=self.workspace_root)

    def purge_duplicates(self) -> int:
        """Purges obsolete duplicate GEMINI.md and AGENTS.md files across workspaces."""
        purged = 0
        protected_files = {
            self.master_protocol_file.resolve(),
            (Path.home() / ".gemini" / "config" / "plugins" / "vespera-overdrive" / "rules" / "AGENTS.md").resolve(),
            (Path.home() / ".gemini" / "config" / "plugins" / "vespera-overdrive" / "rules" / "GEMINI.md").resolve(),
            (Path.home() / ".gemini" / "config" / "AGENTS.md").resolve(),
            (self.workspace_root / "docs" / "AGENTS.md").resolve(),
        }

        for dup in self.duplicate_files_to_purge:
            try:
                if dup.exists():
                    resolved = dup.resolve()
                    if resolved not in protected_files:
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