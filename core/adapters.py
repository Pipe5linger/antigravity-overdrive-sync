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

class GeminiMarkdownAdapter(BaseAdapter):
    """Formats the active context (recent sessions, facts, preferences) into Markdown."""
    def format_context(self):
        import sqlite3
        md = []
        md.append("<SystemMemory>")
        md.append("<!-- DYNAMIC SYSTEM MEMORY ANCHOR - DO NOT MANUAL EDIT -->")
        md.append(f"Last Memory Sync: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                c = conn.cursor()
                
                # 1. Add User Preferences
                c.execute("SELECT pref_key, pref_value FROM preferences")
                prefs = c.fetchall()
                if prefs:
                    md.append("\n### User Preferences")
                    for k, v in prefs:
                        md.append(f"- **{k}**: {v}")
                
                # 2. Add Facts
                c.execute("SELECT fact, confidence FROM facts ORDER BY confidence DESC LIMIT 10")
                facts = c.fetchall()
                if facts:
                    md.append("\n### Extracted Facts")
                    for fact, conf in facts:
                        md.append(f"- {fact} (Confidence: {conf})")
                        
                # 3. Add Recent Sessions
                c.execute("SELECT session_id, topics, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 3")
                sessions = c.fetchall()
                if sessions:
                    md.append("\n### Recent Sessions")
                    for s_id, topics, updated_at in sessions:
                        md.append(f"- **Session {s_id[:8]}** ({updated_at})")
                        md.append(f"  * Topics: {topics}")
        except sqlite3.Error:
            pass
            
        md.append("</SystemMemory>")
        return "\n".join(md)
