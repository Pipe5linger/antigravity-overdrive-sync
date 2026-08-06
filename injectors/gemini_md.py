#!/usr/bin/env python3
"""
Antigravity Overdrive :: Gemini MD Injector
Injects master persona identity and memory structures into GEMINI.md.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.assembler import DynamicPromptAssembler
from injectors.google_docs import GoogleDocsInjector


class GeminiMdInjector:
    def __init__(self, llm_model=None, vector_model=None, workspace_root: Path = None):
        self.workspace_root = Path(workspace_root) if workspace_root else PROJECT_ROOT
        # Root workspace target (D:\AI\GEMINI.md) vs project local target
        root_gemini = Path(r"D:\AI\GEMINI.md")
        if not workspace_root and root_gemini.exists():
            self.target_file = root_gemini
        else:
            self.target_file = self.workspace_root / "GEMINI.md"
        self.assembler = DynamicPromptAssembler(workspace_root=self.workspace_root)

    def inject(self, db=None, dry_run=False) -> bool:
        """Reads target GEMINI.md, preserves memory sections, updates content.

        If a database instance is provided, the injector will generate a full
        Gemini payload (identity, temporal awareness, developer profile metrics,
        facts, recent session summaries, and drive hierarchy) using the same
        logic as :class:`GoogleDocsInjector`. Otherwise, it falls back to the
        original behavior of injecting only the identity header.
        """
        if not self.target_file.exists():
            print(f"[-] GEMINI.md not found at: {self.target_file}")
            return False

        content = self.target_file.read_text(encoding="utf-8")

        header_banner = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n" + "=" * 80 + "\n"
        if db is not None:
            updated_content = f"{header_banner}" + GoogleDocsInjector().compile_google_docs_payload(db)
        else:
            header_banner = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n" + "=" * 80 + "\n"
            payload = self.assembler.build_identity_header()
            if "## HIERARCHICAL MEMORY CORES" in content:
                memory_part = content.split("## HIERARCHICAL MEMORY CORES", 1)[1]
                updated_content = f"{header_banner}{payload}\n## HIERARCHICAL MEMORY CORES{memory_part}"
            else:
                updated_content = f"{header_banner}{payload}"

        if dry_run:
            print(f"[DRY RUN] Would write to: {self.target_file}")
            return True

        self.target_file.write_text(updated_content, encoding="utf-8")
        print(f"[+] Successfully synced: {self.target_file}")
        return True


if __name__ == "__main__":
    injector = GeminiMdInjector()
    injector.inject()