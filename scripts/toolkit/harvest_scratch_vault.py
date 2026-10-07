#!/usr/bin/env python3
"""
File    : harvest_scratch_vault.py
Purpose : Sweeps ephemeral scratch directories across all Antigravity agent sessions,
          extracts AST metadata, docstrings, and signatures, and indexes them into
          the persistent ULM Script Vault in sync_state.db.
"""

import os
import sys
import ast
import hashlib
from pathlib import Path
from datetime import datetime

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except AttributeError:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.database import ULMDatabase

DEFAULT_BRAIN_DIR = Path(r"C:\Users\boben\.gemini\antigravity\brain")
DEFAULT_DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"

def extract_script_metadata(code_content: str, filename: str) -> tuple[str, str]:
    """
    Parses code using AST to extract docstring, functions, classes, imports,
    and infers a category and summary.
    """
    docstring = ""
    functions = []
    classes = []
    imports = []
    
    try:
        tree = ast.parse(code_content)
        docstring = ast.get_docstring(tree) or ""
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except Exception:
        # Fallback to simple top comment extraction if AST parse fails (syntax errors)
        lines = code_content.splitlines()
        comment_lines = []
        for l in lines[:10]:
            l_strip = l.strip()
            if l_strip.startswith("#"):
                comment_lines.append(l_strip.lstrip("#").strip())
        if comment_lines:
            docstring = " ".join(comment_lines)

    # Build meaningful summary
    summary_parts = []
    if docstring:
        summary_parts.append(docstring[:200])
    if functions:
        summary_parts.append(f"Functions: {', '.join(functions[:6])}")
    if classes:
        summary_parts.append(f"Classes: {', '.join(classes[:4])}")
    if imports:
        unique_imports = sorted(list(set(imports)))[:6]
        summary_parts.append(f"Imports: {', '.join(unique_imports)}")

    summary = " | ".join(summary_parts) if summary_parts else f"Utility script: {filename}"

    # Infer Category
    text_corpus = f"{filename} {code_content.lower()} {summary.lower()}"
    if any(k in text_corpus for k in ["sqlite", "sync_state.db", "select ", "pragma", "cursor.execute"]):
        category = "database"
    elif any(k in text_corpus for k in ["cuda", "vram", "torch", "nvml", "rtx 4070", "gpu"]):
        category = "vram_gpu"
    elif any(k in text_corpus for k in ["comfy", "8188", "queue_prompt", "prompt_id", "workflow"]):
        category = "comfyui"
    elif any(k in text_corpus for k in ["transcript", "jsonl", "step_index", "tokens", "turns"]):
        category = "telemetry_logs"
    elif any(k in text_corpus for k in ["benchmark", "latency", "ttft", "perf_counter"]):
        category = "benchmark"
    elif any(k in text_corpus for k in ["git ", "github", "commit", "origin", "branch"]):
        category = "git_github"
    elif any(k in text_corpus for k in ["http", "request", "api", "urllib", "fastapi"]):
        category = "network_api"
    else:
        category = "utility"

    return summary, category

def harvest_scratch_scripts(brain_dir: Path = DEFAULT_BRAIN_DIR, db_path: Path = DEFAULT_DB_PATH, verbose: bool = True):
    """Sweeps all scratch scripts across all session directories into ULMDatabase."""
    if not brain_dir.exists():
        print(f"[-] Brain directory not found at: {brain_dir}")
        return {"scanned": 0, "inserted": 0, "incremented": 0}

    db = ULMDatabase(str(db_path))
    db.initialize_db()

    python_files = list(brain_dir.glob("*/scratch/*.py"))
    # Also check local project scratch directory if present
    local_scratch = PROJECT_ROOT / "scratch"
    if local_scratch.exists():
        python_files.extend(list(local_scratch.glob("*.py")))

    if verbose:
        print(f"[*] Found {len(python_files)} scratch scripts to evaluate across sessions.")

    inserted_count = 0
    incremented_count = 0
    errors_count = 0

    for py_file in python_files:
        try:
            session_id = py_file.parent.parent.name
            code_content = py_file.read_text(encoding="utf-8", errors="ignore")
            if not code_content.strip():
                continue

            summary, category = extract_script_metadata(code_content, py_file.name)
            res = db.upsert_script(
                script_name=py_file.name,
                code_content=code_content,
                docstring_summary=summary,
                category=category,
                source_session=session_id
            )

            if res.get("status") == "inserted":
                inserted_count += 1
            elif res.get("status") == "incremented":
                incremented_count += 1
            else:
                errors_count += 1
        except Exception as e:
            errors_count += 1
            if verbose:
                print(f"[-] Failed indexing {py_file.name}: {e}")

    if verbose:
        print("\n" + "=" * 55)
        print("          ULM SCRIPT VAULT HARVEST COMPLETE")
        print("=" * 55)
        print(f"  • Files Scanned    : {len(python_files)}")
        print(f"  • Unique Indexed   : {inserted_count} new scripts")
        print(f"  • Re-used/Dupes    : {incremented_count} deduplicated")
        print(f"  • Errors           : {errors_count}")
        print("=" * 55 + "\n")

    return {
        "scanned": len(python_files),
        "inserted": inserted_count,
        "incremented": incremented_count,
        "errors": errors_count
    }

if __name__ == "__main__":
    harvest_scratch_scripts()
