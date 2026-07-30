import os
from pathlib import Path
from injectors.base import BaseInjector
from core.assembler import DynamicPromptAssembler

class ClineRulesInjector(BaseInjector):
    """Compiles the dynamic HAMI memory and Vespera baseline rules directly into lightweight Cline workspace rule files."""
    
    def __init__(self, target_file=None, llm_model=None, vector_model=None, top_n=3):
        if not target_file:
            # Targets the workspace root rule paths
            target_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".clinerules")
        super().__init__(target_file)
        self.llm_model = llm_model
        self.vector_model = vector_model
        self.top_n = top_n

    def inject(self, db, dry_run=False):
        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assembler = DynamicPromptAssembler(db.db_path, workspace_root=workspace_root)
        
        projects_dir = r"D:\AI\Projects"
        if not os.path.exists(projects_dir):
            print(f"[-] HAMI: Projects directory {projects_dir} does not exist.")
            return False

        if dry_run:
            sample_content = assembler.assemble_compact_prompt(project_tag="antigravity-overdrive-sync", top_n=self.top_n)
            print("\n[+] --- DRY RUN GENERATED CLINE RULESETS (COMPACT) ---")
            print(sample_content)
            print(f"Would write to all subdirectories of {projects_dir}")
            print("[+] --- END DRY RUN ---")
            return True
            
        success = True
        try:
            from core.utils import atomic_write
            EXCLUDE_DIRS = {"node_modules", ".venv", "venv", "cache", ".git", "__pycache__", "dist", "build", "pip"}
            # Get all subdirectories in D:\AI\Projects
            for item in os.listdir(projects_dir):
                if item.lower() in EXCLUDE_DIRS or item.startswith("."):
                    continue
                sub_path = os.path.join(projects_dir, item)
                if os.path.isdir(sub_path):
                    # Compile project-specific compact prompt
                    compiled_rules = assembler.assemble_compact_prompt(project_tag=item, top_n=self.top_n)
                    
                    clinerules_path = Path(sub_path) / ".clinerules"
                    
                    # If .clinerules is a directory, place AgentProtocols.md inside it; otherwise write directly to .clinerules
                    if clinerules_path.is_dir():
                        target_rule_file = clinerules_path / "AgentProtocols.md"
                    else:
                        target_rule_file = clinerules_path
                    
                    try:
                        atomic_write(str(target_rule_file), compiled_rules)
                        print(f"[+] HAMI: Successfully injected compact rules to {target_rule_file}")
                        # Also keep synced copy in D:\AI\Projects\antigravity-overdrive-sync\db\.clinerules
                        db_clinerules = Path(r"D:\AI\Projects\antigravity-overdrive-sync\db\.clinerules")
                        atomic_write(str(db_clinerules), compiled_rules)
                    except Exception as sub_e:
                        print(f"[-] HAMI: Failed to write to {target_rule_file}: {sub_e}")
                        success = False
            return success
        except Exception as e:
            print(f"[-] HAMI: Failed to inject Cline rules globally: {e}")
            return False

