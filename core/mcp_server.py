#!/usr/bin/env python3
"""
Antigravity Overdrive :: ULM MCP Server
Model Context Protocol (MCP) Server for Universal Local Memory (ULM).
Provides first-class on-demand tools for:
  - Deep semantic & full-text memory recall (ulm_recall)
  - Real-time golden fact pinning (ulm_pin_fact)
  - Procedural graph playbook discovery (ulm_get_playbook)
  - Pre-flight taboo rule syntax validation (ulm_check_taboo)
  - Workload-aware hardware/port status checks (ulm_hardware_status)
"""

import os
import sys
import json
import socket
import sqlite3
import datetime
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except AttributeError:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.database import ULMDatabase, DEFAULT_DB_PATH

# Initialize FastMCP Server
mcp = FastMCP(
    name="ulm-memory",
    instructions="Universal Local Memory (ULM) Cognitive Core & Hardware Telemetry Server"
)

def get_db() -> ULMDatabase:
    """Returns a connected ULMDatabase instance."""
    return ULMDatabase(DEFAULT_DB_PATH)

@mcp.tool()
def ulm_recall(query: str, limit: int = 5, project_tag: str = "") -> str:
    """Performs deep dual-layer hybrid memory recall across historical facts, developer profile metrics,
    and conversational dialogue using both semantic vector embeddings (cosine similarity) and FTS5 BM25 search.

    Args:
        query: The semantic search query or topic to recall (e.g. 'learning rate', 'comfyui vram', 'database schema').
        limit: Maximum number of memories to return (default 5).
        project_tag: Optional project tag filter (e.g. 'antigravity-overdrive-sync', 'ComfyUI', 'AI').
    """
    db = get_db()
    results = []
    seen_facts = set()

    # Layer 1: Semantic Vector Recall (Cosine Similarity via Local Ollama / MemoryConsolidator)
    try:
        from core.consolidator import MemoryConsolidator
        mc = MemoryConsolidator(db)
        query_vector = mc._get_embedding(query)
        if query_vector:
            # Query semantic recall with a permissive threshold for hybrid retrieval
            semantic_matches = db.semantic_recall(query_vector=query_vector, limit=limit, min_similarity=0.35)
            for m in semantic_matches:
                if project_tag and m.get("project_tag") and m.get("project_tag") != project_tag:
                    continue
                tag = f" [{m['project_tag']}]" if m.get("project_tag") else ""
                sim_pct = int(m.get("similarity", 0) * 100)
                results.append(f"- **Semantic Fact**{tag} ({m['category']}, {sim_pct}% match): {m['fact']}")
                seen_facts.add(m['fact'].strip().lower())
    except Exception as e:
        # Graceful degradation to FTS5 if Ollama vector embedding is unavailable
        pass

    # Layer 2: Full-Text Search (FTS5 BM25 Ranked) & Developer Profile Telemetry
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # 2a. Search Facts Table via FTS5 if available or standard LIKE
            try:
                if project_tag:
                    c.execute("""
                        SELECT fact, category, confidence, project_tag, last_seen 
                        FROM facts 
                        WHERE facts MATCH ? AND project_tag = ?
                        ORDER BY confidence DESC, last_seen DESC LIMIT ?
                    """, (query, project_tag, limit))
                else:
                    c.execute("""
                        SELECT fact, category, confidence, project_tag, last_seen 
                        FROM facts 
                        WHERE facts MATCH ? 
                        ORDER BY confidence DESC, last_seen DESC LIMIT ?
                    """, (query, limit))
                rows = c.fetchall()
            except sqlite3.OperationalError:
                like_query = f"%{query}%"
                if project_tag:
                    c.execute("""
                        SELECT fact, category, confidence, project_tag, last_seen 
                        FROM facts 
                        WHERE fact LIKE ? AND project_tag = ?
                        ORDER BY confidence DESC, last_seen DESC LIMIT ?
                    """, (like_query, project_tag, limit))
                else:
                    c.execute("""
                        SELECT fact, category, confidence, project_tag, last_seen 
                        FROM facts 
                        WHERE fact LIKE ? 
                        ORDER BY confidence DESC, last_seen DESC LIMIT ?
                    """, (like_query, limit))
                rows = c.fetchall()

            for r in rows:
                clean_fact = r['fact'].strip().lower()
                if clean_fact not in seen_facts:
                    tag = f" [{r['project_tag']}]" if r['project_tag'] else ""
                    results.append(f"- **Keyword Fact**{tag} ({r['category']}, {int(r['confidence'] * 100)}% conf): {r['fact']}")
                    seen_facts.add(clean_fact)

            # 2b. Search Developer Profile Traits
            like_query = f"%{query}%"
            c.execute("""
                SELECT category, name, description, confidence, frequency 
                FROM developer_profile 
                WHERE name LIKE ? OR description LIKE ? 
                ORDER BY confidence DESC, frequency DESC LIMIT ?
            """, (like_query, like_query, limit))
            for r in c.fetchall():
                results.append(f"- **Developer Profile** [{r['category']} - {r['name']}]: {r['description']}")

            # 2c. Search Historical Chat Messages via FTS5
            try:
                c.execute("""
                    SELECT m.session_id, m.role, m.content, m.created_at, s.project_tag 
                    FROM messages_fts f
                    JOIN messages m ON f.rowid = m.rowid
                    LEFT JOIN sessions s ON m.session_id = s.session_id
                    WHERE messages_fts MATCH ?
                    ORDER BY m.created_at DESC LIMIT 3
                """, (query,))
                for r in c.fetchall():
                    snippet = r['content'].strip().replace("\n", " ")[:140]
                    tag = f" [{r['project_tag']}]" if r['project_tag'] else ""
                    results.append(f"- **Dialogue History**{tag} ({r['created_at'][:10]} {r['role']}): {snippet}...")
            except sqlite3.OperationalError:
                pass

    except Exception as e:
        return f"[-] ULM Recall error: {e}"

    if not results:
        return f"No memories found matching query '{query}' in ULM database."

    return "### 🧠 ULM Memory Recall (Hybrid Results):\n" + "\n".join(results[:limit * 2])

@mcp.tool()
def ulm_pin_fact(fact: str, category: str = "Technical", project_tag: str = "") -> str:
    """Instantly writes a high-weight, immutable golden fact directly into the local SQLite database.
    Pinned facts are immune to temporal decay and pruning.

    Args:
        fact: The factual statement or verified rule to record into persistent memory.
        category: Category classification (e.g. 'Technical', 'Preference', 'Architecture', 'Workflow').
        project_tag: Optional project namespace tag (e.g. 'antigravity-overdrive-sync', 'ComfyUI').
    """
    import hashlib
    db = get_db()
    fact_id = hashlib.sha256(fact.encode("utf-8")).hexdigest()[:16]
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tag = project_tag if project_tag else None

    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at)
                VALUES (?, ?, ?, 1.0, ?, ?, ?, 2.0, 1, ?)
                ON CONFLICT(fact_id) DO UPDATE SET
                    confidence = 1.0,
                    weight = 2.0,
                    pinned = 1,
                    last_seen = excluded.last_seen
            """, (fact_id, fact, category, now_str, now_str, tag, now_str))
        # Compute and cache embedding immediately for instant semantic recall
        try:
            from core.consolidator import MemoryConsolidator
            import numpy as np
            mc = MemoryConsolidator(db)
            emb = mc._get_embedding(fact)
            if emb:
                blob = np.array(emb, dtype=np.float32).tobytes()
                with db.get_connection() as conn:
                    conn.execute("INSERT OR REPLACE INTO fact_embeddings (fact_id, embedding, model_id, created_at) VALUES (?, ?, ?, ?)", (fact_id, blob, "all-minilm", now_str))
                    conn.commit()
        except Exception:
            pass

        tag_str = f" for [{project_tag}]" if project_tag else ""
        return f"[+] Successfully pinned golden fact{tag_str} into ULM memory: \"{fact}\""
    except Exception as e:
        return f"[-] Error pinning fact: {e}"

@mcp.tool()
def ulm_get_playbook(action_name: str) -> str:
    """Discovers and inspects verified local playbooks and recovery scripts from the ULM Procedural Graph.

    Args:
        action_name: The procedure or action name to lookup (e.g. 'vram', 'sync', 'model', 'backup').
    """
    db = get_db()
    results = []

    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            like_term = f"%{action_name}%"
            c.execute("""
                SELECT node_id, action_name, target_script_path, expected_outcome, last_execution_status 
                FROM procedures 
                WHERE action_name LIKE ? OR target_script_path LIKE ?
            """, (like_term, like_term))
            rows = c.fetchall()

            for r in rows:
                status = f" (Last status: {r['last_execution_status']})" if r['last_execution_status'] else ""
                results.append(
                    f"**Playbook**: `{r['action_name']}`{status}\n"
                    f"- Script Path: `{r['target_script_path']}`\n"
                    f"- Expected Outcome: {r['expected_outcome']}"
                )
    except Exception as e:
        return f"[-] Error querying procedural graph: {e}"

    if not results:
        return f"No procedural playbooks found matching '{action_name}'. Check procedures table in sync_state.db."

    return "### 📋 Procedural Playbooks Available:\n\n" + "\n\n".join(results)

@mcp.tool()
def ulm_check_taboo(command: str) -> str:
    """Performs a pre-flight validation check on a CLI or terminal command string 
    against the ULM Taboo Matrix to prevent known syntax landmines and tool execution failures.

    Args:
        command: The terminal command line string planned for execution.
    """
    import re
    db = get_db()
    matched_warnings = []

    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT failure_intent, regex_pattern, remediation, hit_count FROM taboo_rules")
            for r in c.fetchall():
                pattern = r["regex_pattern"]
                if pattern:
                    try:
                        if re.search(pattern, command, re.IGNORECASE):
                            matched_warnings.append(
                                f"⚠️ **TABOO VIOLATION DETECTED** [{r['failure_intent']}]:\n"
                                f"  - Pattern Matched: `{pattern}`\n"
                                f"  - Recommended Remediation: {r['remediation']}"
                            )
                    except re.error:
                        pass
    except Exception as e:
        return f"[-] Taboo check error: {e}"

    if matched_warnings:
        return "\n\n".join(matched_warnings) + "\n\n🚨 **Warning**: Command matches known failure patterns. Modify command before executing."

    return "✅ [PASSED]: Command does not trigger any active Taboo Matrix restrictions."

@mcp.tool()
def ulm_hardware_status() -> str:
    """Checks the real-time operational status of local AI compute ports and services 
    (ComfyUI, SD Forge, Ollama, KoboldCpp) to verify GPU VRAM availability and avoid workload collisions.
    """
    ports = {
        8188: "ComfyUI Workflow Engine",
        7860: "SD Forge WebUI",
        11434: "Ollama Local Inference Server",
        5001: "KoboldCpp Uncensored Server",
        8890: "ULM Dashboard & Webhook API"
    }

    status_lines = []
    active_heavy_workload = False

    for port, name in ports.items():
        is_open = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    is_open = True
        except Exception:
            pass

        if is_open:
            status_lines.append(f"- 🟢 **Port {port}** [{name}]: **ONLINE / ACTIVE**")
            if port in (8188, 7860):
                active_heavy_workload = True
        else:
            status_lines.append(f"- ⚪ **Port {port}** [{name}]: Offline / Inactive")

    arbitration = (
        "⚠️ **Workload Advisory**: Intensive image diffusion engine (ComfyUI / Forge) is ACTIVE. "
        "Suppress or throttle heavy local LLM batch bakes to protect 12GB RTX 4070 VRAM."
        if active_heavy_workload else
        "✅ **Workload Advisory**: GPU VRAM is clear of active diffusion generation. Local LLM operations are safe."
    )

    return "### 🖥️ Workstation Hardware & Service Telemetry:\n" + "\n".join(status_lines) + f"\n\n{arbitration}"

@mcp.tool()
def ulm_comfy_status() -> str:
    """Inspects the active ComfyUI generation queue, currently running prompt, 
    and system node progress directly from http://127.0.0.1:8188.
    """
    import urllib.request
    import urllib.error

    url = "http://127.0.0.1:8188/queue"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Antigravity-ULM"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        running = data.get("queue_running", [])
        pending = data.get("queue_pending", [])

        lines = [
            "### 🎨 ComfyUI Generation Pipeline Status (Port 8188):",
            f"- **Active Prompts Running**: {len(running)}",
            f"- **Queued Tasks Pending**: {len(pending)}"
        ]
        if running:
            for item in running[:3]:
                prompt_id = item[1] if len(item) > 1 else "Unknown"
                lines.append(f"  - ⏳ In Progress: Prompt ID `{prompt_id}`")
        if pending:
            for item in pending[:3]:
                prompt_id = item[1] if len(item) > 1 else "Unknown"
                lines.append(f"  - 🕒 Queued: Prompt ID `{prompt_id}`")

        return "\n".join(lines)
    except urllib.error.URLError:
        return "⚪ ComfyUI is currently OFFLINE or unreachable on http://127.0.0.1:8188."
    except Exception as e:
        return f"[-] Error querying ComfyUI status: {e}"

@mcp.tool()
def ulm_vram_guard(action: str = "check") -> str:
    """Monitors NVIDIA RTX 4070 (12GB) VRAM allocation in real-time and optionally 
    purges PyTorch GPU cache to clear memory spikes before or after diffusion bakes.

    Args:
        action: 'check' to inspect current VRAM telemetry, or 'purge' to force PyTorch cache release.
    """
    import subprocess
    import shutil

    result_lines = ["### ⚡ NVIDIA GPU & VRAM Guard:"]

    # 1. Inspect nvidia-smi if available
    smi_bin = shutil.which("nvidia-smi")
    if smi_bin:
        try:
            out = subprocess.check_output(
                [smi_bin, "--query-gpu=memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
                encoding="utf-8",
                errors="replace",
                timeout=3
            ).strip()
            total, used, free, temp, util = [x.strip() for x in out.split(",")]
            result_lines.extend([
                f"- **VRAM Total**: {int(total):,} MB",
                f"- **VRAM Allocated**: {int(used):,} MB ({int(int(used)/int(total)*100)}%)",
                f"- **VRAM Available**: {int(free):,} MB",
                f"- **GPU Core Temp**: {temp} °C | **Compute Utilization**: {util}%"
            ])
        except Exception as e:
            result_lines.append(f"- Telemetry query error: {e}")
    else:
        result_lines.append("- `nvidia-smi` binary not detected in PATH.")

    # 2. Handle Purge Action
    if action.lower() == "purge":
        try:
            import gc
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                result_lines.append("\n✅ **VRAM Purge Executed**: PyTorch GPU cache and IPC memory successfully released.")
            else:
                result_lines.append("\n⚠️ PyTorch CUDA is not currently initialized in this process.")
        except ImportError:
            result_lines.append("\nℹ️ PyTorch not installed in this environment; memory cleanup relied on GC.")
        except Exception as e:
            result_lines.append(f"\n[-] VRAM Purge error: {e}")

    return "\n".join(result_lines)

@mcp.tool()
def ulm_inspect_db(table: str = "", limit: int = 5, schema: bool = False) -> str:
    """Natively inspects SQLite table statistics, row counts, schema columns, or sample data 
    from sync_state.db without writing or executing ad-hoc Python scripts.

    Args:
        table: Optional table name to inspect. If empty, returns row counts for all tables.
        limit: Number of sample rows to retrieve (default 5).
        schema: If true, returns column names and SQLite data types for the specified table.
    """
    db = get_db()
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            if not table:
                c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [r[0] for r in c.fetchall() if not r[0].startswith("sqlite_")]
                lines = ["### 📊 ULM Database Tables:"]
                for t in tables:
                    try:
                        c.execute(f"SELECT COUNT(*) FROM \"{t}\"")
                        count = c.fetchone()[0]
                        lines.append(f"- **{t}**: {count:,} rows")
                    except Exception as e:
                        lines.append(f"- **{t}**: error ({e})")
                return "\n".join(lines)

            # Specific table
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            valid_tables = {r[0] for r in c.fetchall()}
            if table not in valid_tables:
                return f"Error: Table '{table}' not found in database."

            lines = [f"### 📋 Table: `{table}`"]
            if schema:
                c.execute(f"PRAGMA table_info(\"{table}\")")
                lines.append("\n**Columns:**")
                for col in c.fetchall():
                    pk = " *(PK)*" if col[5] else ""
                    lines.append(f"- `{col[1]}` ({col[2]}){pk}")

            c.execute(f"SELECT * FROM \"{table}\" LIMIT ?", (limit,))
            rows = c.fetchall()
            c.execute(f"PRAGMA table_info(\"{table}\")")
            col_names = [col[1] for col in c.fetchall()]

            if not rows:
                lines.append("\n*(Table is currently empty)*")
            else:
                lines.append(f"\n**Sample Data (Top {len(rows)}):**")
                for i, r in enumerate(rows, 1):
                    lines.append(f"\n*Row {i}:*")
                    for name, val in zip(col_names, r):
                        val_str = str(val)
                        if len(val_str) > 120:
                            val_str = val_str[:117] + "..."
                        lines.append(f"  - `{name}`: {val_str}")

            return "\n".join(lines)
    except Exception as e:
        return f"[-] Error inspecting database: {e}"

@mcp.tool()
def ulm_vacuum_db() -> str:
    """Natively executes an SQLite WAL checkpoint, prunes unlinked orphan embeddings, 
    and vacuums the database to reclaim disk space and maximize query speeds.
    """
    try:
        from scripts.generators_and_tools.vacuum_database import vacuum_database
        from pathlib import Path
        db_path = Path(DEFAULT_DB_PATH)
        orig_size = db_path.stat().st_size
        vacuum_database()
        new_size = db_path.stat().st_size
        freed = (orig_size - new_size) / (1024 * 1024)
        return (
            f"✅ **ULM Vacuum Complete**:\n"
            f"- Prior Size: {orig_size / (1024*1024):.2f} MB\n"
            f"- Current Size: {new_size / (1024*1024):.2f} MB\n"
            f"- Disk Space Reclaimed: {freed:.2f} MB"
        )
    except Exception as e:
        return f"[-] Vacuum error: {e}"

if __name__ == "__main__":
    # Launch stdio transport for native Antigravity MCP integration
    mcp.run(transport="stdio")
