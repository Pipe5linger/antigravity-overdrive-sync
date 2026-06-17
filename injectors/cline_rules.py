import os
from pathlib import Path
from injectors.base import BaseInjector
from core.assembler import DynamicPromptAssembler

class ClineRulesInjector(BaseInjector):
    """Compiles the dynamic HAMI memory and Vespera baseline rules directly into Cline's workspace rule files."""
    
    def __init__(self, target_file=None, llm_model=None, vector_model=None):
        if not target_file:
            # Targets the workspace root rule paths
            target_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".clinerules", "AgentProtocols.md")
        super().__init__(target_file)
        self.llm_model = llm_model
        self.vector_model = vector_model

    def inject(self, db, dry_run=False):
        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assembler = DynamicPromptAssembler(db.db_path, workspace_root=workspace_root)
        
        # Compile prompt assembly
        compiled_system_rules = assembler.assemble_prompt()
        
        # We append the custom tool and workspace constraints for Cline specifically
        cline_header = (
            "# VESPERA SYSTEM PROFILE & DYNAMIC MEMORY\n"
            "<!-- GENERATED AUTOMATICALLY BY HAMI INJECTOR. DO NOT EDIT DIRECTLY. -->\n\n"
        )
        
        full_content = cline_header + compiled_system_rules
        
        if dry_run:
            print("\n[+] --- DRY RUN GENERATED CLINE RULESETS ---")
            print(full_content[:1000] + "\n... [truncated]")
            print("[+] --- END DRY RUN ---")
            return True
            
        try:
            from core.utils import atomic_write
            # Ensure the directory exists
            target_path = Path(self.target_file)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            atomic_write(str(target_path), full_content)
            print(f"[+] HAMI: Successfully injected Vespera memory and persona rules to {target_path}")
            return True
        except Exception as e:
            print(f"[-] HAMI: Failed to inject Cline rules: {e}")
            return False
