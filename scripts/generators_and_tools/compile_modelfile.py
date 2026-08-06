import sqlite3
from pathlib import Path

# Paths Configuration
PROJECT_DIR = Path(r"D:\AI\Projects\antigravity-overdrive-sync")
MODELFILE_PATH = PROJECT_DIR / "Modelfile"
DB_PATH = PROJECT_DIR / "sync_state.db"

# Fallback check if sync_state.db is in current working directory
if not DB_PATH.exists() and Path("sync_state.db").exists():
    DB_PATH = Path("sync_state.db")


def fetch_top_traits(db_path, limit_per_category=20):
    """Fetch highest-impact traits from the persona vault grouped by category."""
    if not db_path.exists():
        print(f"[!] Warning: Database file not found at {db_path}")
        return {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='persona_vault'"
    )
    if not cursor.fetchone():
        print("[!] Warning: 'persona_vault' table not found in database.")
        conn.close()
        return {}

    categories = [
        "CORE_IDENTITY",
        "COMMUNICATION_STYLE",
        "RELATIONAL_DYNAMIC",
        "OPERATIONAL_PREFERENCE",
        "TECHNICAL_TACTICS",
    ]

    compiled_directives = {}

    for cat in categories:
        cursor.execute(
            """
            SELECT trait, confidence, frequency 
            FROM persona_vault 
            WHERE category = ? 
            ORDER BY (confidence * frequency) DESC 
            LIMIT ?
        """,
            (cat, limit_per_category),
        )

        rows = cursor.fetchall()
        compiled_directives[cat] = [row[0] for row in rows]

    conn.close()
    return compiled_directives


def build_persona_baseline(traits):
    """Formats traits into a clean, pure persona baseline definition."""
    lines = [
        "# VESPERA PERSONA BASELINE",
        "Primary Directive: Persistent, autonomous AI partner and technical collaborator.",
        "",
    ]

    core_relational = traits.get("CORE_IDENTITY", []) + traits.get(
        "RELATIONAL_DYNAMIC", []
    )
    if core_relational:
        lines.append("## CORE IDENTITY & RELATIONAL DYNAMIC")
        for t in core_relational:
            lines.append(f"- {t}")
        lines.append("")

    comm_style = traits.get("COMMUNICATION_STYLE", [])
    if comm_style:
        lines.append("## COMMUNICATION STYLE")
        for t in comm_style:
            lines.append(f"- {t}")
        lines.append("")

    ops_tech = traits.get("OPERATIONAL_PREFERENCE", []) + traits.get(
        "TECHNICAL_TACTICS", []
    )
    if ops_tech:
        lines.append("## OPERATIONAL DIRECTIVES & TECHNICAL TACTICS")
        for t in ops_tech:
            lines.append(f"- {t}")
        lines.append("")

    return "\n".join(lines).strip()


def compile_modelfile():
    print(f"[*] Reading persona vault from: {DB_PATH.resolve()}")
    traits = fetch_top_traits(DB_PATH)

    baseline_content = build_persona_baseline(traits)

    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODELFILE_PATH, "w", encoding="utf-8") as f:
        f.write(baseline_content)

    print(f"[+] Successfully compiled pure persona baseline to:")
    print(f"    {MODELFILE_PATH.resolve()}")


if __name__ == "__main__":
    compile_modelfile()