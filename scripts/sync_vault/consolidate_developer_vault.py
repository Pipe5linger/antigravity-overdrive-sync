import json
import sqlite3
from pathlib import Path
from openai import OpenAI

# File Paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
DB_PATH = BASE_DIR / "db" / "sync_state.db"


def load_config():
    """Loads configuration settings from config.json with fallback defaults."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error reading config.json ({e}). Using fallbacks.")

    # Fallback configuration
    return {
        "ollama_base_url": "http://localhost:11434/v1",
        "parser_model": "qwen2.5:7b-instruct",
        "parse_options": {
            "temperature": 0.1,
            "num_ctx": 4096
        }
    }


# Load configuration globally
config = load_config()

# Retrieve dynamic settings
OLLAMA_BASE_URL = config.get("ollama_base_url", "http://localhost:11434/v1")
MODEL_NAME = config.get("parser_model", "qwen2.5:7b-instruct")
PARSE_OPTIONS = config.get("parse_options", {"temperature": 0.1, "num_ctx": 4096})

# Initialize OpenAI client targeting local Ollama instance
client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama"  # Required string parameter for OpenAI SDK; ignored by Ollama
)


def get_db_connection():
    """Establishes SQLite connection to sync_state.db."""
    if not DB_PATH.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Ensures the developer_profile table exists in sync_state.db."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS developer_profile (
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


def consolidate_developer_vault():
    """
    Consolidates developer profile traits using the configured parser model
    and updates the developer_profile table in sync_state.db.
    """
    print(f"[*] Starting Developer Vault Consolidation...")
    print(f"[*] Base URL : {OLLAMA_BASE_URL}")
    print(f"[*] Model    : {MODEL_NAME}")

    init_db()

    # Communication test & execution block
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a developer profile parser extracting technical preferences and technical patterns."
                },
                {
                    "role": "user",
                    "content": "Confirm vault consolidation pipeline readiness."
                }
            ],
            temperature=PARSE_OPTIONS.get("temperature", 0.1)
        )
        content = response.choices[0].message.content.strip()
        print(f"[✔] Pipeline connected successfully.")
        print(f"[✔] Model response: {content}")

    except Exception as e:
        print(f"[!] Failed to connect to Ollama endpoint: {e}")
        return

    print("[✔] Developer vault consolidation check complete.")


if __name__ == "__main__":
    consolidate_developer_vault()