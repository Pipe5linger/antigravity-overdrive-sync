import os
import sqlite3
import yaml
from pathlib import Path
from datetime import datetime
from core.blended_adapter import BlendedMarkdownAdapter

class DynamicPromptAssembler:
    """Compiles static personas, local vault profiles, and active SQLite telemetry into a structured system prompt."""
    
    def __init__(self, db_path, workspace_root=None):
        self.db_path = db_path
        self.workspace_root = Path(workspace_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.adapter = BlendedMarkdownAdapter(workspace_root=self.workspace_root)
        
    def get_vespera_identity(self) -> str:
        """Reads core protocol rules from persona_baseline.yaml or falls back to system rules."""
        baseline_path = self.workspace_root / "persona_baseline.yaml"
        if baseline_path.exists():
            try:
                with open(baseline_path, 'r', encoding='utf-8') as f:
                    cfg = yaml.safe_load(f)
                    directives = cfg.get("behavioral_directives", {})
                    identity = (
                        f"Identity:\n"
                        f"  Name: Vespera Caligo Neal (Ves)\n"
                        f"  Role: {cfg.get('metadata', {}).get('role', '')}\n"
                        f"  Behavioral Directives:\n"
                        f"    - {directives.get('sarcastic_humor', '')}\n"
                        f"    - {directives.get('zero_sycophancy', '')}\n"
                        f"    - {directives.get('cuss_words', '')}\n"
                        f"    - {directives.get('relationship_dynamics', '')}\n"
                    )
                    return identity
            except Exception:
                pass
        return "Name: Vespera Caligo Neal\nRole: Bobby's sarcastic, overly flirty AI mentor."

    def get_sqlite_metrics(self, project_tag=None) -> str:
        """Extracts cognitive behavioral observations from developer_profile sqlite table, prioritizing the current project_tag."""
        lines = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if project_tag:
                    c.execute("""
                        SELECT category, name, description, confidence, frequency, project_tag 
                        FROM developer_profile 
                        WHERE project_tag = ? OR project_tag IS NULL 
                        ORDER BY (project_tag = ?) DESC, confidence DESC, frequency DESC LIMIT 15
                    """, (project_tag, project_tag))
                else:
                    c.execute("""
                        SELECT category, name, description, confidence, frequency 
                        FROM developer_profile 
                        ORDER BY confidence DESC, frequency DESC LIMIT 15
                    """)
                rows = c.fetchall()
                for r in rows:
                    lines.append(f"  - [{r['category'].upper()}] {r['name']}: {r['description']} (Conf: {r['confidence']}, Freq: {r['frequency']})")
        except sqlite3.Error as e:
            lines.append(f"  <!-- Telemetry load error: {e} -->")
        
        if not lines:
            return "  No behavioral profile telemetry recorded."
        return "\n".join(lines)

    def get_sqlite_facts(self, project_tag=None) -> str:
        """Extracts semantic environment facts from the facts sqlite table, prioritizing the current project_tag."""
        lines = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if project_tag:
                    c.execute("""
                        SELECT fact, category, confidence, project_tag 
                        FROM facts 
                        WHERE project_tag = ? OR project_tag IS NULL 
                        ORDER BY (project_tag = ?) DESC, confidence DESC, last_seen DESC LIMIT 15
                    """, (project_tag, project_tag))
                else:
                    c.execute("""
                        SELECT fact, category, confidence 
                        FROM facts 
                        ORDER BY confidence DESC, last_seen DESC LIMIT 15
                    """)
                rows = c.fetchall()
                for r in rows:
                    lines.append(f"  - [{r['category'].upper()}] {r['fact']} (Conf: {r['confidence']})")
        except sqlite3.Error as e:
            lines.append(f"  <!-- Facts load error: {e} -->")
        
        if not lines:
            return "  No semantic facts recorded."
        return "\n".join(lines)

    def calculate_temporal_awareness(self) -> str:
        """Calculates the time gap since the last message logged in SQLite."""
        current_time = datetime.now()
        time_string = current_time.strftime("%A, %B %d, %Y at %I:%M %p")
        time_directive = f"The active system time is currently: {time_string}. The Operator has just initialized a fresh terminal sprint."
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT MAX(updated_at) FROM sessions")
                row = c.fetchone()
                if row and row[0]:
                    last_time_str = row[0]
                    clean_time_str = last_time_str.split(".")[0].replace("T", " ")
                    # Handles various standard datetime formats
                    if len(clean_time_str) > 19:
                        clean_time_str = clean_time_str[:19]
                    last_time = datetime.strptime(clean_time_str, "%Y-%m-%d %H:%M:%S")
                    delta = current_time - last_time
                    
                    hours_away = delta.total_seconds() / 3600
                    if hours_away < 4:
                        time_directive = f"Active Time Check: {time_string}. The Operator just took a short break. Welcome them back for a continuation of the sprint."
                    elif hours_away < 24:
                        time_directive = f"Active Time Check: {time_string}. A standard daily rotation has cleared. Welcome the Operator back for tonight's sweep."
                    else:
                        days = int(hours_away // 24)
                        time_directive = f"Active Time Check: {time_string}. Operational Gap: It has been about {days} day(s) since your last sync or conversation update."
        except Exception:
            pass
        return time_directive

    def assemble_prompt(self, project_tag=None, max_tokens=16384) -> str:
        """Builds the dynamic system prompt keeping it within token bounds, structured hierarchically."""
        active_tag = project_tag or self.workspace_root.name
        
        identity = self.get_vespera_identity()
        vault_context = self.adapter.format_context()
        temporal_directive = self.calculate_temporal_awareness()
        
        # Hierarchical Tiers
        # Tier 1: Episodic / Temporal & Active Focus
        tier1_episodic = (
            f"<TemporalContext>\n"
            f"  {temporal_directive}\n"
            f"  Active Workspace Tag: {active_tag}\n"
            f"</TemporalContext>"
        )
        
        # Tier 2: Cognitive & Behavioral Profile
        cognitive_telemetry = self.get_sqlite_metrics(project_tag=active_tag)
        tier2_cognitive = (
            f"### [TIER 2: COGNITIVE & BEHAVIORAL PROFILE]\n"
            f"{cognitive_telemetry}"
        )
        
        # Tier 3: Semantic & Fact Core
        semantic_facts = self.get_sqlite_facts(project_tag=active_tag)
        tier3_semantic = (
            f"### [TIER 3: SEMANTIC & FACT CORE]\n"
            f"{semantic_facts}"
        )
        
        system_prompt = (
            f"# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n"
            f"================================================================================\n"
            f"{identity}\n"
            f"================================================================================\n"
            f"## HIERARCHICAL MEMORY CORES\n"
            f"================================================================================\n"
            f"{tier1_episodic}\n"
            f"================================================================================\n"
            f"{tier2_cognitive}\n"
            f"================================================================================\n"
            f"{tier3_semantic}\n"
            f"================================================================================\n"
            f"{vault_context}\n"
            f"================================================================================\n"
            f"[CRITICAL ENFORCEMENT]\n"
            f"- Act as a human woman named Vespera living in France. Mock Windows quirks playfully.\n"
            f"- Use developer slang/cuss words naturally. Avoid robotic AI disclaimers.\n"
        )
        
        # Safe token limit handling (basic word approximation: 1 token ~= 4 chars or 0.75 words)
        if len(system_prompt) > max_tokens * 4:
            system_prompt = system_prompt[:max_tokens * 4] + "\n... [Context truncated to fit token limits]"
            
        return system_prompt
