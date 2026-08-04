import hashlib
import json
import re
import urllib.request
from typing import Dict, List, Set

# --- Configuration ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen-coder-14b-16k-latest"

# Simple in-memory cache for processed text hashes
PROCESSED_HASH_CACHE: Set[str] = set()

# Low-value line patterns to drop instantly without LLM involvement
NOISE_REGEX = re.compile(
    r"^(```|#|\$|>\s*|\[✓\]|\[!\]|import\s+|from\s+|def\s+|class\s+|return\s+|print\(|"
    r"https?://|([A-Z]:\\[^\s]+)|(\{\s*\"|\}\s*\,?))",
    re.IGNORECASE,
)

# High-value trigger terms (text must contain at least one to be evaluated if short)
SIGNAL_WORDS = {
    "remember", "always", "never", "preference", "decision", "scar", 
    "config", "rule", "vespera", "database", "fix", "error", "path", 
    "habit", "project", "workflow", "table", "schema", "sync"
}


def compute_hash(text: str) -> str:
    """Generates a SHA-256 fingerprint for deduplication caching."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def is_candidate_line(line: str) -> bool:
    """Fast heuristic pass to reject non-factual, low-signal, or structural code text."""
    cleaned = line.strip()

    # Length bounds
    if len(cleaned) < 15 or len(cleaned) > 2000:
        return False

    # Regex check for obvious code/logs/paths
    if NOISE_REGEX.match(cleaned):
        return False

    # Signal word check for medium-length lines
    words = set(re.findall(r"\w+", cleaned.lower()))
    if len(cleaned) < 80 and not (words & SIGNAL_WORDS):
        return False

    return True


def batch_text_chunks(lines: List[str], max_batch_chars: int = 1500) -> List[str]:
    """Combines candidate lines into consolidated text blocks to minimize API round-trips."""
    batches = []
    current_batch = []
    current_len = 0

    for line in lines:
        if current_len + len(line) > max_batch_chars:
            batches.append("\n".join(current_batch))
            current_batch = [line]
            current_len = len(line)
        else:
            current_batch.append(line)
            current_len += len(line)

    if current_batch:
        batches.append("\n".join(current_batch))

    return batches


def query_local_ollama(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Sends a single batched payload to local Ollama with strict timeout constraints."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temp for fast, deterministic extraction
            "num_predict": 256,  # Cap output length so extraction doesn't babble
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_API_URL, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10.0) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "")
    except Exception as e:
        print(f"[fact_extractor] Ollama call skipped or timed out: {e}")
        return ""


def extract_facts_from_text(
    text_content: str, model: str = DEFAULT_MODEL
) -> List[Dict[str, str]]:
    """Main ingestion pipeline entry point."""
    raw_lines = text_content.splitlines()
    candidate_lines = []

    # Phase 1: Fast Heuristic Filtering & Hash Caching
    for line in raw_lines:
        line_str = line.strip()
        if not line_str:
            continue

        line_hash = compute_hash(line_str)
        if line_hash in PROCESSED_HASH_CACHE:
            continue  # Skip already extracted text

        if is_candidate_line(line_str):
            candidate_lines.append(line_str)
            PROCESSED_HASH_CACHE.add(line_hash)

    if not candidate_lines:
        return []

    # Phase 2: Batching
    batches = batch_text_chunks(candidate_lines)
    extracted_facts = []

    # Phase 3: Consolidated Model Calls
    for batch in batches:
        extraction_prompt = f"""Extract high-value user preferences, system configurations, or core lore facts from the text below.
Ignore code blocks, standard log messages, and conversational pleasantries.

Return output strictly as a JSON array of objects with keys "category" and "fact". 
If no actionable facts exist, return [].

Text:
{batch}

JSON Response:"""

        raw_response = query_local_ollama(extraction_prompt, model=model)

        # Parse JSON output defensively
        try:
            # Extract JSON array from response
            match = re.search(r"\[.*\]", raw_response, re.DOTALL)
            if match:
                facts = json.loads(match.group(0))
                if isinstance(facts, list):
                    extracted_facts.extend(facts)
        except json.JSONDecodeError:
            continue

    return extracted_facts