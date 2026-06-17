import os
import yaml
import datetime

class BaseAdapter:
    def __init__(self, db):
        self.db = db

    def format_context(self):
        raise NotImplementedError("Adapters must implement format_context()")

class ContinueConfigAdapter(BaseAdapter):
    """Formats recent facts and preferences to inject into Continue's config.yaml system prompt."""
    def format_context(self):
        # Build system message extensions
        system_additions = ["\n[System Memory Ledger]"]
        
        import sqlite3
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                c = conn.cursor()
                
                # Fetch preferences
                c.execute("SELECT pref_key, pref_value FROM preferences")
                prefs = c.fetchall()
                if prefs:
                    system_additions.append("\nPreferences:")
                    for k, v in prefs:
                        system_additions.append(f"- {k}: {v}")
                
                # Fetch top facts
                c.execute("SELECT fact FROM facts ORDER BY confidence DESC LIMIT 10")
                facts = c.fetchall()
                if facts:
                    system_additions.append("\nKey Facts:")
                    for (fact,) in facts:
                        system_additions.append(f"- {fact}")
        except sqlite3.Error as e:
            print(f"[-] Adapter SQL Error: {e}")

        return "\n".join(system_additions)

class OllamaModelfileAdapter(BaseAdapter):
    """Formats recent facts/preferences as Modelfile SYSTEM instructions."""
    def format_context(self):
        import sqlite3
        modelfile_lines = []
        
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT fact FROM facts ORDER BY confidence DESC LIMIT 10")
                facts = c.fetchall()
                
                if facts:
                    modelfile_lines.append("# ULM INJECTED SYSTEM MEMORY")
                    for (fact,) in facts:
                        modelfile_lines.append(f"SYSTEM \"Memory Anchor: {fact}\"")
        except sqlite3.Error:
            pass
            
        return "\n".join(modelfile_lines)

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
