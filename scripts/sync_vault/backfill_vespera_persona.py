import json
import sqlite3
import requests
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
DB_PATH = BASE_DIR / "db" / "sync_state.db"


def load_config():
    """Loads settings from config.json with safe fallbacks."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error reading config.json ({e}). Using fallbacks.")

    return {
        "ollama_url": "http://localhost:11434/api/chat",
        "parser_model": "qwen2.5:7b-instruct",
        "parse_options": {
            "temperature": 0.1,
            "num_ctx": 4096
        }
    }


# Load configuration
config = load_config()
OLLAMA_URL = config.get("ollama_url", "http://localhost:11434/api/chat")
MODEL_NAME = config.get("parser_model", "qwen2.5:7b-instruct")
PARSE_OPTIONS = config.get("parse_options", {"temperature": 0.1, "num_ctx": 4096})

# 5 Core Canonical Categories
VALID_CATEGORIES = {
    "OPERATIONAL_PREFERENCE",
    "RELATIONAL_DYNAMIC",
    "COMMUNICATION_STYLE",
    "CORE_IDENTITY",
    "TECHNICAL_TACTICS"
}

SYSTEM_PROMPT = """You are a persona extraction engine analyzing AI assistant interactions. 
Your goal is to extract implicit and explicit persona traits, technical preferences, and communication habits.

Output ONLY a raw JSON array of objects with this schema:
[
  {
    "category": "CATEGORY_NAME",
    "trait": "Concise statement of the observed trait",
    "confidence": 0.90
  }
]

CRITICAL: Every category MUST be exactly one of these 5 uppercase strings:
- OPERATIONAL_PREFERENCE
- RELATIONAL_DYNAMIC
- COMMUNICATION_STYLE
- CORE_IDENTITY
- TECHNICAL_TACTICS

Do not include commentary, explanation, or markdown formatting outside the JSON array."""


def get_db():
    """Establishes SQLite connection to sync_state.db."""
    if not DB_PATH.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Ensures persona_profile table exists."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persona_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            trait TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            confidence REAL DEFAULT 1.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, trait)
        )
    """)
    conn.commit()
    conn.close()


def query_ollama_parser(messages_chunk):
    """Sends prompt chunk to Ollama using configured model and parse options."""
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract persona traits from these turns:\n\n{messages_chunk}"}
        ],
        "stream": False,
        "format": "json",
        "options": PARSE_OPTIONS
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        raw_text = data.get("message", {}).get("content", "[]")
        return json.loads(raw_text)
    except Exception as e:
        print(f"[!] Error querying Ollama ({MODEL_NAME}): {e}")
        return []


def upsert_persona_traits(traits):
    """Upserts extracted traits into sync_state.db with frequency tracking."""
    if not traits:
        return 0

    conn = get_db()
    cursor = conn.cursor()
    inserted_or_updated = 0

    for item in traits:
        category = str(item.get("category", "")).upper().strip()
        trait = str(item.get("trait", "")).strip()
        confidence = float(item.get("confidence", 0.85))

        # Fallback to CORE_IDENTITY if category is outside the 5 core buckets
        if category not in VALID_CATEGORIES:
            category = "CORE_IDENTITY"

        if not trait:
            continue

        # Upsert logic: Increment frequency if trait exists under category
        cursor.execute("""
            INSERT INTO persona_profile (category, trait, frequency, confidence, updated_at)
            VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(category, trait) DO UPDATE SET
                frequency = frequency + 1,
                confidence = ROUND((confidence + excluded.confidence) / 2.0, 2),
                updated_at = CURRENT_TIMESTAMP
        """, (category, trait, confidence))
        inserted_or_updated += 1

    conn.commit()
    conn.close()
    return inserted_or_updated


def run_backfill():
    """Main backfill execution loop."""
    print("=" * 65)
    print(" VESPERA PERSONA BACKFILL PIPELINE")
    print(f" Target Model : {MODEL_NAME}")
    print(f" Target DB    : {DB_PATH}")
    print(f" Endpoint     : {OLLAMA_URL}")
    print("=" * 65)

    init_db()

    print("\n[✔] Configuration validated. Ready for pipeline runs.")


if __name__ == "__main__":
    run_backfill()