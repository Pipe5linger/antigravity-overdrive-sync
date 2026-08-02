import argparse
import sqlite3
from pathlib import Path

CATEGORIES = [
    "CORE_IDENTITY",
    "RELATIONAL_DYNAMIC",
    "COMMUNICATION_STYLE",
    "OPERATIONAL_PREFERENCE",
    "TECHNICAL_TACTICS",
]

CATEGORY_TITLES = {
    "CORE_IDENTITY": "Core Identity & Archetype",
    "RELATIONAL_DYNAMIC": "Relational Dynamics & Alignment",
    "COMMUNICATION_STYLE": "Communication Style & Tone",
    "OPERATIONAL_PREFERENCE": "Operational Preferences & Execution",
    "TECHNICAL_TACTICS": "Technical Tactics & Methodologies",
}


def fetch_top_traits(db_path: Path, max_per_category: int = 12) -> dict:
    """Queries top persona traits sorted by frequency and confidence."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    traits_by_cat = {cat: [] for cat in CATEGORIES}

    # Query top traits per category ordered by frequency and confidence
    cursor.execute("""
        SELECT category, trait, frequency, confidence 
        FROM persona_profile 
        ORDER BY frequency DESC, confidence DESC
    """)
    rows = cursor.fetchall()

    for category, trait, freq, conf in rows:
        cat_key = category.upper().strip() if category else "CORE_IDENTITY"
        if cat_key not in traits_by_cat:
            cat_key = "CORE_IDENTITY"

        # Limit count per category to prevent context bloat
        if len(traits_by_cat[cat_key]) < max_per_category:
            # Simple check to avoid near-identical strings in the top list
            if not any(trait.lower()[:30] == existing.lower()[:30] for existing in traits_by_cat[cat_key]):
                traits_by_cat[cat_key].append(trait)

    conn.close()
    return traits_by_cat


def generate_markdown_prompt(traits_by_cat: dict) -> str:
    """Generates a clean, curated persona prompt."""
    lines = ["# VESPERA PERSONA SPECIFICATION\n"]
    lines.append("<vespera_persona>")

    for cat in CATEGORIES:
        traits = traits_by_cat.get(cat, [])
        if not traits:
            continue

        title = CATEGORY_TITLES.get(cat, cat.replace("_", " ").title())
        lines.append(f"\n## {title}")
        for trait in traits:
            lines.append(f"- {trait}")

    lines.append("\n</vespera_persona>")
    return "\n".join(lines)


def generate_modelfile(
    markdown_prompt: str, base_model: str, context_window: int, temperature: float
) -> str:
    """Wraps the compiled prompt inside an Ollama Modelfile."""
    return f"""FROM {base_model}

# Runtime Parameters
PARAMETER num_ctx {context_window}
PARAMETER temperature {temperature}

# System Persona Directive
SYSTEM \"\"\"
{markdown_prompt}
\"\"\"
"""


def main():
    parser = argparse.ArgumentParser(
        description="Compile Vespera persona from sync_state.db"
    )
    parser.add_argument(
        "--db-path",
        default=r"d:\AI\Projects\antigravity-overdrive-sync\db\sync_state.db",
        help="Path to target SQLite database",
    )
    parser.add_argument(
        "--ollama",
        action="store_true",
        help="Output an Ollama Modelfile instead of persona_prompt.md",
    )
    parser.add_argument(
        "--max-traits",
        type=int,
        default=12,
        help="Maximum traits per category bucket",
    )
    parser.add_argument(
        "--base-model",
        default="qwen-coder-14b-16k-latest",
        help="Base model for Modelfile",
    )
    args = parser.parse_args()

    db_file = Path(args.db_path)
    traits = fetch_top_traits(db_file, max_per_category=args.max_traits)
    markdown_prompt = generate_markdown_prompt(traits)

    if args.ollama:
        out_content = generate_modelfile(
            markdown_prompt, args.base_model, 16384, 0.7
        )
        default_out = "Modelfile"
    else:
        out_content = markdown_prompt
        default_out = "persona_prompt.md"

    out_path = db_file.parent.parent / default_out
    out_path.write_text(out_content, encoding="utf-8")

    print(f"[✓] Clean persona successfully compiled to: {out_path}")


if __name__ == "__main__":
    main()