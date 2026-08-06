import re
from typing import List, Tuple, Dict, Any


class FactExtractor:
    """
    Tier 1 (Regex/Keyword) & Tier 2 (Caching) signal extractor.
    Tightened to prevent standard coding, terminal logs, and casual dev chatter
    from triggering LLM evaluations.
    """

    # --- HIGH-SIGNAL PATTERNS ---
    # Must represent persistent user identity, environment configs, or explicit rules.
    PROFILE_PATTERNS = [
        # 1. Identity & Personal Info
        r"\b(my name is|call me|i am|i'm)\s+[A-Z][a-z]+",
        r"\b(i live in|located in|my time\s?zone|based in)\b",
        
        # 2. Preferences & Behavioral Rules (Subject-Bound)
        r"\b(i prefer|i like|i hate|i dislike|i favor|my preferred)\b",
        r"\b(always use|never use|don'?t use|make sure to use|avoid using)\b",
        r"\b(my style is|code style|indentation style)\b",
        
        # 3. Specific Infrastructure & Environment Setup
        r"\bmy (server|setup|port|database|db|config|api\s?key|local model|drive|path)\b",
        r"\b(running on port|hosted at|located at [a-z]:[\\/]|drive letter)\b",
        r"\b(comfyui|ollama|openrouter|vsc|cline|gguf|lora|sqlite|wal)\b",  # Specific ecosystem tools
        
        # 4. Explicit Retention / Memory Commands
        r"\b(remember that|keep in mind|note that|save this|for future reference)\b",
        r"\b(don'?t forget|add to (my )?profile|update (my )?profile)\b",
    ]

    # --- EXCLUSION PATTERNS ---
    # Fast bypass for standard git commands, terminal outputs, and stack traces.
    EXCLUDE_PATTERNS = [
        r"^\s*[$>]?\s*(git|npm|yarn|pnpm|pip|cargo|python|node|docker)\s+",
        r"^\s*(Traceback \(most recent call last\)|File \".*\", line \d+)",
        r"^\s*(ERROR|WARN|DEBUG|INFO)\s+\[",
        r"^\s*```(json|bash|sh|powershell|python)?$",
    ]

    def __init__(self):
        # Pre-compile regexes for sub-millisecond execution
        self.signal_regex = re.compile(
            "|".join(self.PROFILE_PATTERNS), re.IGNORECASE
        )
        self.exclude_regex = re.compile(
            "|".join(self.EXCLUDE_PATTERNS), re.IGNORECASE
        )

    def get_candidates(self, dialogue: str) -> List[Tuple[int, str]]:
        """
        Scans dialogue for high-signal lines while ignoring standard CLI noise.
        Returns a list of tuples: (line_index, line_text)
        """
        candidates = []
        lines = dialogue.splitlines()

        for idx, line in enumerate(lines):
            cleaned = line.strip()

            # Skip empty lines, very short responses, or standard shell output
            if not cleaned or len(cleaned) < 8:
                continue
            if self.exclude_regex.search(cleaned):
                continue

            # Evaluate against high-signal patterns
            if self.signal_regex.search(cleaned):
                # Optionally include 1 line of surrounding context for context preservation
                prev_line = lines[idx - 1].strip() if idx > 0 else ""
                next_line = lines[idx + 1].strip() if idx < len(lines) - 1 else ""
                
                excerpt = f"{prev_line}\n{cleaned}\n{next_line}".strip()
                candidates.append((idx, excerpt))

        return candidates

    def has_signal(self, dialogue: str) -> bool:
        """
        Fast Boolean check: Returns True if session contains actionable candidates.
        """
        return len(self.get_candidates(dialogue)) > 0