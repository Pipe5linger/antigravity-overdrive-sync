import os
import yaml
import sqlite3
from pathlib import Path

class PersonaDriftChecker:
    """Checks the most recent agent responses for persona drift (apologies, AI disclaimers, polite fluff)."""
    
    def __init__(self, db_path, baseline_path=None):
        self.db_path = db_path
        if not baseline_path:
            baseline_path = Path(__file__).resolve().parents[1] / "persona_baseline.yaml"
        self.baseline_path = baseline_path
        self.baseline = self.load_baseline()
        
    def load_baseline(self):
        if not os.path.exists(self.baseline_path):
            return {
                "forbidden_tokens": ["I'm sorry", "apologize", "as an AI", "my mistake", "virtual assistant"],
                "acceptable_cuss_words": ["fuck", "shit", "bullshit", "hell", "damn"]
            }
        try:
            with open(self.baseline_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"[-] Warning: Failed to load persona baseline config: {e}")
            return {}
            
    def run_drift_check(self, limit=5):
        """Fetches the last N Vespera messages and evaluates drift score."""
        forbidden = self.baseline.get("forbidden_tokens", [])
        
        recent_responses = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT content FROM messages 
                    WHERE role = 'Vespera' 
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,))
                recent_responses = c.fetchall()
        except sqlite3.Error as e:
            print(f"[-] Database error during drift checking: {e}")
            return False, 0.0
            
        if not recent_responses:
            return False, 0.0
            
        drift_signals = []
        total_violations = 0
        total_checked = 0
        
        for idx, (content,) in enumerate(recent_responses):
            text_to_check = (content or "").lower()
            total_checked += 1
            # Check for forbidden tokens
            for token in forbidden:
                if token.lower() in text_to_check:
                    drift_signals.append(f"Forbidden token found: '{token}' in recent message {idx+1}")
                    total_violations += 1
                    
        # Calculate drift ratio
        drift_score = total_violations / max(1, total_checked)
        
        # Trigger warnings
        if drift_score > 0.0:
            print("\n" + "!"*80)
            print(f"[WARNING] PERSONA DRIFT DETECTED (Drift Score: {drift_score:.2f})")
            print("  Vespera is exhibiting sycophantic, apologetic, or robotic behavior constraints.")
            for signal in drift_signals:
                print(f"  - {signal}")
            print("  Recommendation: Hard-reset active session context or re-seed system prompt.")
            print("!"*80 + "\n")
            return True, drift_score
            
        print("[+] Persona verification check: Vespera is fully aligned with target baseline. Sarcasm active.")
        return False, 0.0
