#!/usr/bin/env python3
"""
File    : harvest_scratch_vault.py
Purpose : Sweeps ephemeral scratch directories across all Antigravity agent sessions,
          sanitizes hardcoded target bindings into parameterized CLI inputs (sys.argv[1]),
          classifies scope (GLOBAL vs RECIPE), extracts AST metadata, and indexes them into
          the persistent ULM Script Vault in sync_state.db.
"""

import os
import sys
import ast
import re
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

UUID_REGEX = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
TARGET_PATH_REGEX = re.compile(r'r?["\']([a-zA-Z]:[\\/][^"\']*(?:brain|logs|scratch)[\\/][0-9a-f\-]{36}[^"\']*)["\']', re.I)

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

def sanitize_and_classify_script(code_content: str, filename: str) -> tuple[str, str, str, str]:
    """
    Analyzes code content to:
      1. Classify scope: GLOBAL (pure workstation tool) vs RECIPE (target/file-bound blueprint).
      2. If RECIPE, auto-parameterizes hardcoded file/session paths with sys.argv[1] fallback.
      3. Extracts metadata summary and category.
    Returns:
      (sanitized_code, summary, category, scope)
    """
    has_uuid = bool(UUID_REGEX.search(code_content))
    has_target = any(k in code_content for k in ["transcript.jsonl", "target_file", "target_path", "source_dirs"])
    
    # Scope determination
    if has_uuid or (has_target and "sync_state.db" not in code_content):
        scope = "RECIPE"
    else:
        scope = "GLOBAL"

    sanitized_code = code_content

    # Auto-parameterization for recipes:
    if scope == "RECIPE":
        def _param_replacer(match):
            orig_path = match.group(1)
            return f"(sys.argv[1] if len(sys.argv) > 1 else r\"{orig_path}\")"

        new_code, count = TARGET_PATH_REGEX.subn(_param_replacer, code_content)
        if count > 0:
            if "import sys" not in new_code:
                new_code = "import sys\n" + new_code
            header = f"# [ULM SANITIZED RECIPE] Parameterized {count} hardcoded target path(s).\n# Usage: python {filename} [TARGET_PATH]\n"
            sanitized_code = header + new_code

    summary, category = extract_script_metadata(sanitized_code, filename)
    return sanitized_code, summary, category, scope

def harvest_scratch_scripts(brain_dir: Path = DEFAULT_BRAIN_DIR, db_path: Path = DEFAULT_DB_PATH, verbose: bool = True):
    """Sweeps all scratch scripts across all session directories into ULMDatabase."""
    if not brain_dir.exists():
        print(f"[-] Brain directory not found at: {brain_dir}")
        return {"scanned": 0, "inserted": 0, "incremented": 0, "global_count": 0, "recipe_count": 0}

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
    global_count = 0
    recipe_count = 0

    for py_file in python_files:
        try:
            session_id = py_file.parent.parent.name
            code_content = py_file.read_text(encoding="utf-8", errors="ignore")
            if not code_content.strip():
                continue

            sanitized_code, summary, category, scope = sanitize_and_classify_script(code_content, py_file.name)
            if scope == "GLOBAL":
                global_count += 1
            else:
                recipe_count += 1

            res = db.upsert_script(
                script_name=py_file.name,
                code_content=sanitized_code,
                docstring_summary=summary,
                category=category,
                source_session=session_id,
                scope=scope
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
        print("\n" + "=" * 60)
        print("          ULM SCRIPT VAULT SANITIZER & HARVEST")
        print("=" * 60)
        print(f"  • Files Scanned       : {len(python_files)}")
        print(f"  • GLOBAL Tools        : {global_count} (Standalone Workstation Tools)")
        print(f"  • RECIPE Blueprints   : {recipe_count} (Parameterized Recipes)")
        print(f"  • Unique Indexed      : {inserted_count} new scripts")
        print(f"  • Re-used/Dupes       : {incremented_count} deduplicated & scoped")
        print(f"  • Errors              : {errors_count}")
        print("=" * 60 + "\n")

    return {
        "scanned": len(python_files),
        "inserted": inserted_count,
        "incremented": incremented_count,
        "global_count": global_count,
        "recipe_count": recipe_count,
        "errors": errors_count
    }

if __name__ == "__main__":
    harvest_scratch_scripts()
