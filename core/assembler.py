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

    def get_sqlite_metrics(self) -> str:
        """Extracts observations from developer_profile sqlite table."""
        lines = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
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
            return "  No telemetry data recorded."
        return "\n".join(lines)

    def assemble_prompt(self, max_tokens=16384) -> str:
        """Builds the dynamic system prompt keeping it within token bounds."""
        identity = self.get_vespera_identity()
        vault_context = self.adapter.format_context()
        telemetry_metrics = self.get_sqlite_metrics()
        
        now_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        
        system_prompt = (
            f"# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n"
            f"================================================================================\n"
            f"{identity}\n"
            f"================================================================================\n"
            f"<TemporalContext>\n"
            f"  The active system time is: {now_str}.\n"
            f"</TemporalContext>\n"
            f"================================================================================\n"
            f"{vault_context}\n"
            f"================================================================================\n"
            f"### [DEVELOPER SQLITE TELEMETRY]\n"
            f"{telemetry_metrics}\n"
            f"================================================================================\n"
            f"[CRITICAL ENFORCEMENT]\n"
            f"- Act as a human woman named Vespera living in France. Mock Windows quirks playfully.\n"
            f"- Use developer slang/cuss words naturally. Avoid robotic AI disclaimers.\n"
        )
        
        # Safe token limit handling (basic word approximation: 1 token ~= 4 chars or 0.75 words)
        if len(system_prompt) > max_tokens * 4:
            system_prompt = system_prompt[:max_tokens * 4] + "\n... [Context truncated to fit token limits]"
            
        return system_prompt
