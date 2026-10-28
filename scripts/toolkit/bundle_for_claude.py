import os
import sys
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Target files that define the complete ULM architecture & threat model
CORE_FILES = [
    ("main.py", "CLI entry point and command router"),
    ("web_server.py", "FastAPI local control center & REST API"),
    ("core/engine.py", "ULM orchestrator & sliding window manager"),
    ("core/database.py", "SQLite engine, WAL mode, FTS5 triggers, thread-local connection pool"),
    ("core/assembler.py", "Dynamic prompt assembler, rules injector & context budgeter"),
    ("core/consolidator.py", "Fact deduplication, conflict resolution & memory aging"),
    ("core/daemon.py", "Background directory watcher & real-time sync daemon"),
    ("core/mcp_server.py", "FastMCP server exposing memory tools to AI agents"),
    ("core/procedural_runner.py", "Procedural Graph script execution engine (Audited for RCE)"),
    ("scripts/playbooks/procedure_helpers.py", "Audited procedural action helpers (no shell execution, no inline -c)"),
    ("core/utils.py", "Atomic writes, file hashers, safe normalizers"),
    ("scripts/generators_and_tools/taboo_extractor.py", "Graveyard Miner & Taboo Protocol (Audited for Memory Poisoning)"),
    ("tests/test_security_audit_remediations.py", "Regression test suite proving all audit remediations")
]

def generate_claude_bundle():
    root = Path(__file__).resolve().parent.parent.parent
    evidence_dir = root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    out_file = evidence_dir / "ULM_CORE_ARCHITECTURE_BUNDLE.md"

    print("=" * 65)
    print(" 📦 PACKAGING ULM CORE CODEBASE FOR CLAUDE AUDIT")
    print("=" * 65)

    buffer = []
    buffer.append("# UNIVERSAL LOCAL MEMORY (ULM) - COMPLETE CORE ENGINE BUNDLE")
    buffer.append(f"> Generated for Line-Level Adversarial Audit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    buffer.append("> Repository: https://github.com/Pipe5linger/antigravity-overdrive-sync\n")
    buffer.append("## Executive Architectural Summary")
    buffer.append("ULM is a local-first, zero-cloud cognitive memory engine for coding agents (Antigravity, Cline, Gemini).")
    buffer.append("Key subsystems included in this audit bundle:")
    buffer.append("- **Storage Engine**: SQLite in WAL mode with PRAGMA busy_timeout=5000 and FTS5 triggers (`core/database.py`).")
    buffer.append("- **Context Control**: Rolling 4,500-token sliding window + dynamic rule injection (`core/assembler.py`, `core/engine.py`).")
    buffer.append("- **Tool Protocol**: FastMCP server providing bidirectional semantic memory tools (`core/mcp_server.py`).")
    buffer.append("- **Threat Boundaries**: Procedural Graph execution (`core/procedural_runner.py`) and Graveyard Miner stderr taboo rules (`scripts/generators_and_tools/taboo_extractor.py`).\n")
    buffer.append("---\n")

    total_lines = 0
    total_bytes = 0

    for rel_path, desc in CORE_FILES:
        file_path = root / rel_path
        if not file_path.exists():
            print(f"[!] Warning: File missing: {rel_path}")
            continue

        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = len(content.splitlines())
        size_kb = file_path.stat().st_size / 1024
        total_lines += lines
        total_bytes += file_path.stat().st_size

        print(f" [+] Bundled: {rel_path:45s} ({lines:5d} lines | {size_kb:5.1f} KB)")

        buffer.append(f"## File: `{rel_path}`")
        buffer.append(f"**Purpose**: {desc}")
        buffer.append(f"**Lines**: {lines} | **Size**: {size_kb:.1f} KB\n")
        buffer.append("```python")
        buffer.append(content)
        buffer.append("```\n")
        buffer.append("---\n")

    out_file.write_text("\n".join(buffer), encoding="utf-8")

    bundle_size_kb = out_file.stat().st_size / 1024
    print("=" * 65)
    print(f" [✓] BUNDLE READY: {out_file.name}")
    print(f"     Path:  {out_file}")
    print(f"     Total: {len(CORE_FILES)} files | {total_lines:,} lines | {bundle_size_kb:.1f} KB (~55k tokens)")
    print("=" * 65)
    print("\n💡 HOW TO SHARE WITH CLAUDE:")
    print("   1. Open Claude chat in your browser.")
    print(f"   2. Drag and drop this single file into the chat:\n      {out_file}")
    print("   3. Paste this prompt:")
    print("      'Here is the complete source code for the ULM core engine, database layer,")
    print("       and threat boundaries. Please perform your full line-level adversarial audit.'")
    print("=" * 65)

if __name__ == "__main__":
    generate_claude_bundle()

