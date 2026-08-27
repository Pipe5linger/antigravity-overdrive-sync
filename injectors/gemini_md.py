#!/usr/bin/env python3
"""
Antigravity Overdrive :: Gemini MD Injector
Injects master persona identity and memory structures into GEMINI.md across both:
  1. Global Machine-Wide scope: ~/.gemini/GEMINI.md and ~/.gemini/config/AGENTS.md
  2. Workspace scope: D:/AI/GEMINI.md (and local workspace root)
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.assembler import DynamicPromptAssembler
from injectors.google_docs import GoogleDocsInjector


class GeminiMdInjector:
    def __init__(self, llm_model=None, vector_model=None, workspace_root: Path = None):
        self.workspace_root = Path(workspace_root) if workspace_root else PROJECT_ROOT
        
        # Primary sync targets: Global ~/.gemini/GEMINI.md, ~/.gemini/config/AGENTS.md, and Workspace D:\AI\GEMINI.md
        self.target_files = []
        
        # 1. Global Machine-Wide Targets
        home_dir = Path.home()
        global_gemini_dir = home_dir / ".gemini"
        if global_gemini_dir.exists():
            self.target_files.append(global_gemini_dir / "GEMINI.md")
            
        global_config_dir = global_gemini_dir / "config"
        self.target_files.append(global_config_dir / "AGENTS.md")
        
        # 2. Workspace AI Lab Target (D:/AI/GEMINI.md)
        root_gemini = Path(r"D:\AI\GEMINI.md")
        if root_gemini.exists() and root_gemini not in self.target_files:
            self.target_files.append(root_gemini)
            
        # 3. Local Project Target (if specific workspace provided)
        local_gemini = self.workspace_root / "GEMINI.md"
        if local_gemini not in self.target_files:
            self.target_files.append(local_gemini)

        self.assembler = DynamicPromptAssembler(workspace_root=self.workspace_root)

    def inject(self, db=None, dry_run=False) -> bool:
        """Generates the master persona payload and syncs it to all global and workspace targets."""
        header_banner = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n" + "=" * 80 + "\n"
        
        if db is not None:
            updated_content = f"{header_banner}" + GoogleDocsInjector().compile_google_docs_payload(db)
        else:
            payload = self.assembler.build_identity_header()
            updated_content = f"{header_banner}{payload}"

        success = True
        synced_count = 0

        for target in self.target_files:
            if dry_run:
                print(f"[DRY RUN] Would write to: {target}")
                continue

            try:
                # Ensure parent directory exists
                target.parent.mkdir(parents=True, exist_ok=True)
                
                # If target already has custom memory cores and no db was provided, preserve them
                if db is None and target.exists():
                    try:
                        existing_text = target.read_text(encoding="utf-8")
                        if "## HIERARCHICAL MEMORY CORES" in existing_text:
                            memory_part = existing_text.split("## HIERARCHICAL MEMORY CORES", 1)[1]
                            file_payload = f"{header_banner}{self.assembler.build_identity_header()}\n## HIERARCHICAL MEMORY CORES{memory_part}"
                        else:
                            file_payload = updated_content
                    except Exception:
                        file_payload = updated_content
                else:
                    file_payload = updated_content

                with open(target, "w", encoding="utf-8") as f:
                    f.write(file_payload)
                    
                print(f"[+] Successfully synced: {target}")
                synced_count += 1
            except Exception as e:
                print(f"[-] Failed to sync {target}: {e}")
                success = False

        print(f"[+] Synced persona protocol across {synced_count} global & workspace target(s).")
        return success


if __name__ == "__main__":
    injector = GeminiMdInjector()
    injector.inject()