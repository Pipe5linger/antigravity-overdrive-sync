from pathlib import Path

class BlendedMarkdownAdapter:
    """Formats context by reading from the .vespera_memory vault files."""
    def __init__(self, workspace_root=None):
        self.vault_dir = Path(workspace_root or ".") / ".vespera_memory"

    def format_context(self) -> str:
        md = ["\n<!-- SYSTEM MEMORY VAULT COMPILATION -->"]
        
        files_to_load = [
            ("current_context.md", "Active Work Frame"),
            ("project_ledger.md", "Repository Milestones"),
            ("post_mortems.md", "System Post-Mortems & Guards"),
            ("developer_profile.md", "Developer Profile & Metrics")
        ]
        
        for filename, title in files_to_load:
            path = self.vault_dir / filename
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8").strip()
                    if content:
                        md.append(f"\n### [{title.upper()}]\n{content}\n")
                except Exception as e:
                    md.append(f"\n<!-- Error loading {filename}: {e} -->")
                    
        return "\n".join(md)