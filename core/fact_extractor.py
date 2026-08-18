import re
import hashlib
import json
import requests
from typing import List, Tuple, Dict, Any
from pathlib import Path

# Module-level cache for global deduplication
PROCESSED_HASH_CACHE = set()

class FactExtractor:
    """
    Tier 1 (Regex/Keyword), Tier 2 (SHA-256 Caching), and Tier 3 Signal Extractor.
    Filters standard coding, terminal logs, and CLI noise while extracting high-value facts.
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

        # 5. Persona & Lore Anchor Signals
        r"\b(vespera|st\.? jude|scar|trauma|meltdown|mccallister|mentor)\b",
    ]

    # --- EXCLUSION PATTERNS ---
    # Fast bypass for standard git commands, terminal outputs, stack traces, and code noise.
    EXCLUDE_PATTERNS = [
        r"^\s*[$>]?\s*(git|npm|yarn|pnpm|pip|cargo|python|node|docker)\s+",
        r"^\s*(Traceback \(most recent call last\)|File \".*\", line \d+)",
        r"^\s*(ERROR|WARN|DEBUG|INFO)\s*(\[|\d|:)",
        r"^\s*\[(INFO|DEBUG|WARN|ERROR)\].*",
        r"^\s*```(json|bash|sh|powershell|python)?$",
        r"^\s*[{}[\]\",]+\s*$",
        r"^\s*import\s+\w+",
        r"^\s*from\s+\w+\s+import",
        r"^\s*def\s+\w+\(",
        r"^[A-Z]:\\[^:\n]+\.py$",
    ]

    def __init__(self):
        # Pre-compile regexes for sub-millisecond execution
        self.signal_regex = re.compile(
            "|".join(self.PROFILE_PATTERNS), re.IGNORECASE
        )
        self.exclude_regex = re.compile(
            "|".join(self.EXCLUDE_PATTERNS), re.IGNORECASE
        )
        self.telemetry = {
            "tier1_dropped": 0,
            "tier2_hits": 0,
            "tier3_extracted": 0,
        }
        self.local_hash_cache = set()

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

    def extract(self, payload: str) -> List[Dict[str, Any]]:
        """
        3-Tier Ingestion and Extraction Pipeline:
        - Tier 1: Regex & Heuristic Pre-filter (drops noise, logs, syntax)
        - Tier 2: SHA-256 Deduplication (avoids re-processing seen candidates)
        - Tier 3: Signal Extraction into Fact structured items
        """
        extracted_facts = []
        lines = payload.splitlines()

        for idx, line in enumerate(lines):
            cleaned = line.strip()

            # Tier 1 Filter: Skip empty, short, or noise-matching lines
            if not cleaned or len(cleaned) < 10 or self.exclude_regex.search(cleaned) or not self.signal_regex.search(cleaned):
                self.telemetry["tier1_dropped"] += 1
                continue

            # Tier 2 Filter: SHA-256 Deduplication
            line_hash = hashlib.sha256(cleaned.lower().encode("utf-8")).hexdigest()
            if line_hash in self.local_hash_cache or line_hash in PROCESSED_HASH_CACHE:
                self.telemetry["tier2_hits"] += 1
                continue

            self.local_hash_cache.add(line_hash)
            PROCESSED_HASH_CACHE.add(line_hash)

            # Tier 3: Extract structured fact
            category = "technical"
            lower_line = cleaned.lower()
            if any(k in lower_line for k in ["vespera", "scar", "trauma", "mentor", "origin", "mccallister"]):
                category = "persona"
            elif any(k in lower_line for k in ["prefer", "like", "hate", "dislike", "style", "never use", "always use"]):
                category = "preference"

            fact_entry = {
                "fact": cleaned,
                "category": category,
                "confidence": 0.95
            }
            extracted_facts.append(fact_entry)
            self.telemetry["tier3_extracted"] += 1

        return extracted_facts


def extract_facts_from_text(text: str) -> List[Dict[str, Any]]:
    """Helper function to extract facts from raw text using FactExtractor."""
    extractor = FactExtractor()
    return extractor.extract(text)


def extract_and_embed_facts(messages: List[dict], llm_model: str) -> Tuple[List[str], List[List[float]], List[dict]]:
    """Extracts facts from message logs and generates fallback embeddings for legacy ingestion."""
    documents = []
    embeddings = []
    metadatas = []

    if not messages:
        return ["System log recorded"], [[0.0] * 768], [{"category": "Technical", "source": "antigravity_ulm"}]

    extractor = FactExtractor()
    combined_text = "\n".join([m.get("text", "") or m.get("content", "") for m in messages if isinstance(m, dict)])
    facts = extractor.extract(combined_text)

    if not facts:
        facts = [{"fact": "System log recorded", "category": "Technical"}]

    for item in facts:
        fact_text = item.get("fact", "System log recorded")
        category = item.get("category", "Technical")
        documents.append(fact_text)
        embeddings.append([0.0] * 768)
        metadatas.append({"category": category, "source": "antigravity_ulm"})

    return documents, embeddings, metadatas