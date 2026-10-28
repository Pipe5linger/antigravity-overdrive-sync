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
import regex  # Hard requirement for ReDoS-safe taboo execution

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

def expand_conversational_query(raw_query: str) -> dict:
    """Pre-processes and cleans conversational user queries into targeted retrieval tokens,
    stripping stop-words, extracting key entities, and generating resilient FTS5 queries."""
    import re
    
    stop_words = {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", 
        "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", 
        "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", 
        "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", 
        "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", 
        "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", 
        "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "please", "same", 
        "see", "settings", "setting", "should", "show", "so", "some", "such", "tell", "than", "that", 
        "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this", 
        "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were", "what", 
        "when", "where", "which", "while", "who", "whom", "why", "with", "would", "you", "your", 
        "yours", "yourself", "yourselves"
    }
    
    # Strip special punctuation while preserving dashes, underscores, and dots in filenames
    cleaned = re.sub(r'[^\w\s\-_.]', ' ', raw_query)
    raw_tokens = [t.strip().lower() for t in cleaned.split() if t.strip()]
    
    meaningful = [t for t in raw_tokens if t not in stop_words and len(t) > 1]
    if not meaningful:
        meaningful = raw_tokens
        
    fts_parts = []
    for t in meaningful:
        clean_t = t.replace('"', '').replace("'", "")
        if clean_t:
            fts_parts.append(f'"{clean_t}"*')
            
    fts_query = " OR ".join(fts_parts) if fts_parts else raw_query
    
    return {
        "raw_query": raw_query,
        "meaningful_tokens": meaningful,
        "fts_query": fts_query
    }

@mcp.tool()
def ulm_recall(query: str, limit: int = 5, project_tag: str = "") -> str:
    """Performs doctoral-grade hybrid memory recall across historical facts, developer profile metrics,
    relational procedural playbooks, and conversational dialogue using RRF (Reciprocal Rank Fusion)
    over dense vector embeddings (cosine distance) and FTS5 BM25 lexical search with recency decay.

    Args:
        query: The semantic search query or topic to recall (e.g. 'learning rate', 'comfyui vram', 'database schema').
        limit: Maximum number of memories to return (default 5).
        project_tag: Optional project tag filter (e.g. 'antigravity-overdrive-sync', 'ComfyUI', 'AI').
    """
    db = get_db()
    results = []
    exp = expand_conversational_query(query)
    meaningful_tokens = exp["meaningful_tokens"]
    fts_query = exp["fts_query"]
    
    candidates = {}  # fact_id -> dict

    # Layer 1: Semantic Vector Recall (Cosine Distance via Local Ollama / MiniLM)
    try:
        from core.consolidator import MemoryConsolidator
        mc = MemoryConsolidator(db)
        ollama_endpoint = db.get_preference("ollama_endpoint", "http://localhost:11434")
        if mc._is_ollama_running(ollama_endpoint):
            query_vector = mc._get_embedding(query)
            if query_vector:
                semantic_matches = db.semantic_recall(query_vector=query_vector, limit=limit * 2, min_similarity=0.32)
                for rank, m in enumerate(semantic_matches, start=1):
                    if project_tag and m.get("project_tag") and m.get("project_tag") != project_tag:
                        continue
                    fid = m.get("fact_id") or str(rank)
                    candidates[fid] = {
                        "fact": m["fact"],
                        "category": m["category"],
                        "confidence": m.get("confidence", 1.0) or 1.0,
                        "project_tag": m.get("project_tag", "") or "",
                        "last_seen": m.get("last_seen"),
                        "created_at": m.get("created_at"),
                        "pinned": m.get("pinned", 0) or 0,
                        "source_pointer": m.get("source_pointer", "") or "",
                        "sim": m.get("similarity", 0.0),
                        "rrf_score": 0.5 / (60 + rank),
                        "hit_type": "semantic"
                    }
    except Exception:
        pass

    # Layer 2: Full-Text Search (FTS5 BM25 Ranked) on facts_fts & Fallback Token Matching
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            fts_rows = []
            try:
                if project_tag:
                    c.execute("""
                        SELECT f.fact_id, f.fact, f.category, f.confidence, f.project_tag, 
                               f.last_seen, f.pinned, f.weight, f.created_at, f.source_pointer,
                               bm25(facts_fts) as rank_score
                        FROM facts_fts fts
                        JOIN facts f ON fts.fact_id = f.fact_id
                        WHERE facts_fts MATCH ? AND f.project_tag = ? AND (f.origin != 'agent_pending' OR f.origin IS NULL)
                        ORDER BY rank_score ASC LIMIT ?
                    """, (fts_query, project_tag, limit * 2))
                else:
                    c.execute("""
                        SELECT f.fact_id, f.fact, f.category, f.confidence, f.project_tag, 
                               f.last_seen, f.pinned, f.weight, f.created_at, f.source_pointer,
                               bm25(facts_fts) as rank_score
                        FROM facts_fts fts
                        JOIN facts f ON fts.fact_id = f.fact_id
                        WHERE facts_fts MATCH ? AND (f.origin != 'agent_pending' OR f.origin IS NULL)
                        ORDER BY rank_score ASC LIMIT ?
                    """, (fts_query, limit * 2))
                fts_rows = c.fetchall()
            except sqlite3.OperationalError:
                fts_rows = []

            # If FTS yielded few results, fallback to token-based LIKE queries
            if len(fts_rows) < limit:
                for token in meaningful_tokens[:4]:
                    wildcard = f"%{token}%"
                    if project_tag:
                        c.execute("""
                            SELECT fact_id, fact, category, confidence, project_tag, 
                                   last_seen, pinned, weight, created_at, source_pointer, 0.0 as rank_score
                            FROM facts 
                            WHERE fact LIKE ? AND project_tag = ? AND (origin != 'agent_pending' OR origin IS NULL)
                            ORDER BY confidence DESC, last_seen DESC LIMIT ?
                        """, (wildcard, project_tag, limit))
                    else:
                        c.execute("""
                            SELECT fact_id, fact, category, confidence, project_tag, 
                                   last_seen, pinned, weight, created_at, source_pointer, 0.0 as rank_score
                            FROM facts 
                            WHERE fact LIKE ? AND (origin != 'agent_pending' OR origin IS NULL)
                            ORDER BY confidence DESC, last_seen DESC LIMIT ?
                        """, (wildcard, limit))
                    extra_rows = c.fetchall()
                    fts_rows.extend(extra_rows)

            for rank, r in enumerate(fts_rows, start=1):
                fid = r["fact_id"] or f"fts_{rank}"
                if fid in candidates:
                    candidates[fid]["rrf_score"] += 0.5 / (60 + rank)
                    candidates[fid]["hit_type"] = "hybrid"
                    if not candidates[fid].get("source_pointer") and r["source_pointer"]:
                        candidates[fid]["source_pointer"] = r["source_pointer"]
                else:
                    candidates[fid] = {
                        "fact": r["fact"],
                        "category": r["category"],
                        "confidence": r["confidence"] or 1.0,
                        "project_tag": r["project_tag"] or "",
                        "last_seen": r["last_seen"],
                        "created_at": r["created_at"],
                        "pinned": r["pinned"] or 0,
                        "source_pointer": r["source_pointer"] or "",
                        "sim": 0.0,
                        "rrf_score": 0.5 / (60 + rank),
                        "hit_type": "keyword"
                    }

            # Recency Decay and Pinned Prioritization Scoring
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            for fid, item in candidates.items():
                score = item["rrf_score"]
                date_str = item.get("last_seen") or item.get("created_at")
                if date_str:
                    try:
                        clean_date = date_str.replace("Z", "+00:00")
                        dt = datetime.datetime.fromisoformat(clean_date)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=datetime.timezone.utc)
                        days_old = max(0.0, (now_dt - dt).total_seconds() / 86400.0)
                        if days_old <= 3.0:
                            score += 0.015  # Fresh within 72h
                        elif days_old <= 14.0:
                            score += 0.008  # Fresh within 2 weeks
                    except Exception:
                        pass

                if item.get("pinned"):
                    score += 0.025  # Pinned golden invariant boost
                    
                score *= (item.get("confidence") or 1.0)
                item["final_score"] = score

            # Sort and format top facts
            sorted_candidates = sorted(candidates.values(), key=lambda x: x["final_score"], reverse=True)
            for item in sorted_candidates[:limit]:
                tag = f" [{item['project_tag']}]" if item.get("project_tag") else ""
                ptr = f" *(Ground-Truth: `{item['source_pointer']}`)*" if item.get("source_pointer") else ""
                pinned_badge = " 📌" if item.get("pinned") else ""
                sim_str = f", {int(item['sim']*100)}% sim" if item.get("sim") else ""
                results.append(f"- **{item['hit_type'].capitalize()} Fact**{pinned_badge}{tag} ({item['category']}{sim_str}): {item['fact']}{ptr}")

            # Layer 3: Search Developer Profile Traits
            for token in meaningful_tokens[:2]:
                wildcard = f"%{token}%"
                c.execute("""
                    SELECT category, name, description, confidence, frequency 
                    FROM developer_profile 
                    WHERE name LIKE ? OR description LIKE ? 
                    ORDER BY confidence DESC, frequency DESC LIMIT 2
                """, (wildcard, wildcard))
                for r in c.fetchall():
                    results.append(f"- **Developer Profile** [{r['category']} - {r['name']}]: {r['description']}")

            # Layer 4: Search Historical Chat Messages via FTS5 using fts_query
            try:
                c.execute("""
                    SELECT f.session_id, f.role, f.content, f.created_at, s.project_tag 
                    FROM messages_fts f
                    LEFT JOIN sessions s ON f.session_id = s.session_id
                    WHERE messages_fts MATCH ?
                    ORDER BY f.created_at DESC LIMIT 2
                """, (fts_query,))
                for r in c.fetchall():
                    snippet = r['content'].strip().replace("\n", " ")[:140]
                    tag = f" [{r['project_tag']}]" if r['project_tag'] else ""
                    results.append(f"- **Dialogue History**{tag} ({r['created_at'][:10]} {r['role']}): {snippet}...")
            except sqlite3.OperationalError:
                pass

            # Layer 5: Relational Triad Linkage (Procedures & Script Vault Ground-Truth)
            triad_notes = []
            for token in meaningful_tokens[:3]:
                wildcard = f"%{token}%"
                c.execute("""
                    SELECT action_name, target_script_path, expected_outcome, last_execution_status
                    FROM procedures
                    WHERE action_name LIKE ? OR target_script_path LIKE ?
                    LIMIT 1
                """, (wildcard, wildcard))
                proc = c.fetchone()
                if proc:
                    status_lbl = f" | Status: `{proc['last_execution_status']}`" if proc['last_execution_status'] else ""
                    triad_notes.append(f"🛠️ **Linked Procedure**: `{proc['action_name']}` -> `{proc['target_script_path']}`{status_lbl}")
                    break

            try:
                vault_matches = db.search_scripts(query=" ".join(meaningful_tokens), limit=1)
                if vault_matches:
                    vm = vault_matches[0]
                    triad_notes.append(f"📦 **Linked Script Vault**: `{vm['script_name']}` ({vm['category']}) - {vm['docstring_summary'][:100]}...")
            except Exception:
                pass

            if triad_notes:
                results.append("\n" + "\n".join(triad_notes))

    except Exception as e:
        return f"[-] ULM Recall error: {e}"

    if not results:
        return f"No memories found matching query '{query}' in ULM database."

    return "### 🧠 ULM Memory Recall (Doctoral RRF Hybrid Results):\n" + "\n".join(results)

@mcp.tool()
def ulm_pin_fact(fact: str, category: str = "Technical", project_tag: str = "", source_pointer: str = "") -> str:
    """Proposes a new factual statement or verified rule to record into persistent ULM memory.
    All agent-generated facts are quarantined with provenance 'agent_pending' (pinned=0) 
    and require human authorization via the WebUI or TUI to become immutable pinned rules.

    Args:
        fact: The factual statement or verified rule to record into persistent memory.
        category: Category classification (e.g. 'Technical', 'Preference', 'Architecture', 'Workflow', 'System_Rule').
        project_tag: Optional project namespace tag (e.g. 'antigravity-overdrive-sync', 'ComfyUI').
        source_pointer: Optional ground-truth pointer to source code, script path, or documentation (e.g. 'scripts/facial_parity.py:L45', 'port 8188').
    """
    import hashlib
    import re
    db = get_db()
    fact_id = db.make_fact_id(fact)
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tag = project_tag if project_tag else None

    # Hard boundary: Agent invocations CANNOT create pinned facts or claim 'user' provenance
    pinned_val = 0
    weight_val = 1.0
    origin_val = "agent_pending"

    # Auto-detect ground-truth source pointer if not explicitly supplied
    pointer = source_pointer.strip() if source_pointer else ""
    if not pointer:
        path_match = re.search(r'([a-zA-Z0-9_\-\./\\]+\.(?:py|json|md|bat|ps1|sh|yaml|yml)(?::L\d+)?)', fact)
        if path_match:
            pointer = path_match.group(1)
        else:
            port_match = re.search(r'(?:port|localhost:)\s*(\d+)', fact, re.IGNORECASE)
            if port_match:
                pointer = f"port:{port_match.group(1)}"

    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at, source_pointer, origin)
                VALUES (?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_id) DO UPDATE SET
                    confidence = 1.0,
                    weight = CASE WHEN facts.origin = 'user' THEN facts.weight ELSE excluded.weight END,
                    pinned = facts.pinned,
                    source_pointer = COALESCE(excluded.source_pointer, facts.source_pointer),
                    origin = facts.origin,
                    last_seen = excluded.last_seen
            """, (fact_id, fact, category, now_str, now_str, tag, weight_val, pinned_val, now_str, pointer if pointer else None, origin_val))
        # Compute and cache embedding immediately for semantic recall
        try:
            from core.consolidator import MemoryConsolidator
            import numpy as np
            mc = MemoryConsolidator(db)
            ollama_endpoint = db.get_preference("ollama_endpoint", "http://localhost:11434")
            vector_model = db.get_preference("vector_model", "nomic-embed-text:latest")
            if mc._is_ollama_running(ollama_endpoint):
                emb = mc._get_embedding(fact)
                if emb:
                    blob = np.array(emb, dtype=np.float32).tobytes()
                    with db.get_connection() as conn:
                        conn.execute("""
                            INSERT INTO fact_embeddings (fact_id, embedding, model_id, created_at)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(fact_id) DO UPDATE SET
                                embedding = excluded.embedding,
                                model_id = excluded.model_id,
                                created_at = excluded.created_at
                        """, (fact_id, blob, vector_model, now_str))
                        conn.commit()
        except Exception:
            pass

        tag_str = f" for [{project_tag}]" if project_tag else ""
        ptr_str = f" [Anchor: `{pointer}`]" if pointer else ""
        return f"[+] Fact recorded into ULM{tag_str}{ptr_str} with provenance 'agent_pending' (pinned=0, weight=1.0). Requires human confirmation via WebUI/TUI to elevate to permanent immutable pinned status (pinned=1): \"{fact}\""
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
def ulm_recall_script(query: str, limit: int = 3, category: str = "", scope: str = "", include_code: bool = True) -> str:
    """Recalls verified, previously generated scratch scripts and utilities from the ULM Script Vault
    to eliminate token waste and prevent rewriting throwaway Python scripts.

    Args:
        query: Semantic or keyword search query (e.g. 'inspect table columns', 'check vram', 'parse transcripts').
        limit: Maximum number of scripts to return (default 3).
        category: Optional category filter ('database', 'vram_gpu', 'comfyui', 'telemetry_logs', 'benchmark', 'utility').
        scope: Optional scope filter ('GLOBAL' for workstation tools, 'RECIPE' for target-bound blueprints).
        include_code: Whether to include the full runnable code content in the output (default True).
    """
    db = get_db()
    matches = db.search_scripts(query=query, limit=limit, category=category, scope=scope)
    if not matches:
        return f"No scripts found in vault matching '{query}'. Try a broader query or check ulm_get_playbook."

    blocks = []
    for m in matches:
        scope_val = m.get('scope', 'GLOBAL') or 'GLOBAL'
        hdr = f"#### 🛠️ `{m['script_name']}` [{scope_val}] (Category: `{m['category']}` | ID: `{m['script_id']}` | Uses: {m['execution_count']})"
        desc = f"**Summary**: {m['docstring_summary']}"
        if scope_val == "RECIPE":
            desc += "\n> [!TIP] Parameterized Recipe: Accepts target file/directory as `sys.argv[1]`."
        if include_code and m.get("code_content"):
            code = f"```python\n{m['code_content']}\n```"
            blocks.append(f"{hdr}\n{desc}\n\n{code}")
        else:
            blocks.append(f"{hdr}\n{desc}")

    return f"### 📦 ULM Script Vault ({len(matches)} Matches for '{query}'):\n\n" + "\n\n---\n\n".join(blocks)

@mcp.tool()
def ulm_check_taboo(command: str) -> str:
    """Performs a pre-flight validation check on a CLI or terminal command string 
    against the ULM Taboo Matrix to prevent known syntax landmines and tool execution failures.

    Args:
        command: The terminal command line string planned for execution.
    """
    db = get_db()
    matched_warnings = []

    # ReDoS and payload cap defense: Limit search input size to 2048 chars
    bounded_command = str(command)[:2048]

    def _safe_match(pat: str, text: str, timeout_sec: float = 0.05) -> bool:
        # regex module natively supports timeout at C level, dropping GIL and interrupting runaway backtracking
        return bool(regex.search(pat, text, flags=regex.IGNORECASE, timeout=timeout_sec))

    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT failure_intent, regex_pattern, remediation, hit_count FROM taboo_rules")
            rules = c.fetchall()

        for r in rules:
            pattern = r["regex_pattern"]
            # Skip null, empty, or excessively long regex patterns (>200 chars)
            if not pattern or len(pattern) > 200:
                continue
            try:
                matched = _safe_match(pattern, bounded_command, timeout_sec=0.05)
                if matched:
                    matched_warnings.append(
                        f"⚠️ **TABOO VIOLATION DETECTED** [{r['failure_intent']}]:\n"
                        f"  - Pattern Matched: `{pattern}`\n"
                        f"  - Recommended Remediation: {r['remediation']}"
                    )
            except TimeoutError:
                matched_warnings.append(
                    f"⚠️ **TABOO REGEX TIMEOUT** [{r['failure_intent']}]: Pattern exceeded 50ms safety deadline."
                )
            except regex.error:
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

    # Inspect real-time GPU VRAM & utilization via nvidia-smi (catches ai-toolkit / training runs)
    import subprocess
    import shutil
    vram_used_mb = 0
    vram_total_mb = 12282
    gpu_util_pct = 0
    smi_bin = shutil.which("nvidia-smi")
    if smi_bin:
        try:
            out = subprocess.check_output(
                [smi_bin, "--query-gpu=memory.total,memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                encoding="utf-8",
                errors="replace",
                timeout=2
            ).strip()
            parts = [x.strip() for x in out.splitlines()[0].split(",")]
            if len(parts) >= 3:
                vram_total_mb = int(parts[0])
                vram_used_mb = int(parts[1])
                gpu_util_pct = int(parts[2])
                status_lines.append(
                    f"- ⚡ **RTX 4070 Telemetry**: `{vram_used_mb:,} / {vram_total_mb:,} MB` VRAM ({int(vram_used_mb / max(1, vram_total_mb) * 100)}%) | Compute: `{gpu_util_pct}%`"
                )
                if vram_used_mb > 2500 or gpu_util_pct > 25:
                    active_heavy_workload = True
        except Exception:
            pass

    arbitration = (
        f"⚠️ **Workload Advisory**: Heavy GPU workload active ({vram_used_mb:,} MB VRAM allocated, {gpu_util_pct}% compute). "
        "Suppress or throttle heavy local LLM/diffusion bakes to protect 12GB RTX 4070 VRAM."
        if active_heavy_workload else
        "✅ **Workload Advisory**: GPU VRAM is clear of active heavy compute or diffusion generation. Local LLM operations are safe."
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
        import urllib.request
        import urllib.error
        purge_notes = []
        # A. Trigger ComfyUI server-side VRAM purge if running on 127.0.0.1:8188
        try:
            free_payload = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:8188/free",
                data=free_payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    purge_notes.append("✅ **ComfyUI VRAM Purge**: Models unloaded and server VRAM released (:8188).")
        except urllib.error.URLError:
            purge_notes.append("ℹ️ ComfyUI server not running or unreachable on :8188 (skipped).")
        except Exception as ce:
            purge_notes.append(f"[-] ComfyUI /free API error: {ce}")

        # B. Local process PyTorch cache and Python garbage collection
        try:
            import gc
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                purge_notes.append("✅ **Local PyTorch Cache Purged**: GPU cache & IPC memory cleared.")
        except ImportError:
            pass
        except Exception as e:
            purge_notes.append(f"[-] Local PyTorch cleanup error: {e}")

        if purge_notes:
            result_lines.append("\n" + "\n".join(purge_notes))

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
                from core.utils import scrub_secrets
                SENSITIVE_PREF_KEYWORDS = {"key", "secret", "token", "password", "api_key", "credentials", "webhook"}
                SENSITIVE_COL_KEYWORDS = {"secret", "token", "password", "credentials"}
                for i, r in enumerate(rows, 1):
                    lines.append(f"\n*Row {i}:*")
                    row_dict = dict(zip(col_names, r))
                    for name, val in row_dict.items():
                        is_sensitive = False
                        if table.lower() == "preferences":
                            if name.lower() == "pref_value":
                                pref_k = str(row_dict.get("pref_key", "")).lower()
                                is_sensitive = any(s in pref_k for s in SENSITIVE_PREF_KEYWORDS)
                        else:
                            is_sensitive = any(s in name.lower() for s in SENSITIVE_COL_KEYWORDS)

                        if is_sensitive and val:
                            val_str = "********"
                        else:
                            val_str = scrub_secrets(str(val))
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



@mcp.tool()
def ulm_park_thought(thought: str, project_tag: str = "", priority: str = "normal", source_context: str = "") -> str:
    """Parks a casual thought, idea, tangent, or reminder to revisit later.
    Use this immediately when Bobby mentions something off-hand, a future optimization,
    or a task that shouldn't derail the current immediate objective.
    
    Args:
        thought: The reminder or idea to park.
        project_tag: Optional project namespace (e.g. 'ai-toolkit', 'comfyui', 'antigravity-overdrive-sync').
        priority: Priority tag ('normal', 'high', 'urgent'). Default 'normal'.
        source_context: Optional context snippet (e.g. 'working on config.yaml', 'debugging CUDA OOM').
    """
    try:
        db = get_db()
        thought_id = db.park_thought(
            thought=thought,
            context_project=project_tag,
            priority=priority,
            source_context=source_context
        )
        return f"Successfully parked thought #{thought_id} under project '{project_tag or 'global'}': '{thought}'"
    except Exception as e:
        return f"[-] Error parking thought: {e}"

@mcp.tool()
def ulm_get_open_loops(project_tag: str = "", status: str = "parked", limit: int = 10, mark_reminded: bool = False) -> str:
    """Retrieves pending parked thoughts / open loops to surface back to Bobby.
    Use this during downtime, natural conversation breaks, or at the conclusion of a task
    to see if there are loose ends or off-hand thoughts to revisit.
    
    Args:
        project_tag: Optional project filter (e.g. 'ai-toolkit', 'comfyui'). If omitted, retrieves all.
        status: Filter by status ('parked', 'resolved', 'dropped'). Default 'parked'.
        limit: Max items to return. Default 10.
        mark_reminded: If True, increments the reminded counter on returned thoughts.
    """
    try:
        db = get_db()
        loops = db.get_open_loops(context_project=project_tag, status=status, limit=limit)
        if not loops:
            return "No open loops or parked thoughts found."
        
        lines = [f"Found {len(loops)} open loop(s):"]
        for item in loops:
            tid = item["id"]
            if mark_reminded:
                db.touch_thought_reminder(tid)
            proj = f"[{item['context_project']}] " if item.get("context_project") else ""
            prio = f"({item['priority'].upper()}) " if item.get("priority") != "normal" else ""
            lines.append(f"- #{tid}: {prio}{proj}{item['thought']} (created: {item.get('created_at', 'unknown')}, reminded: {item.get('reminded_count', 0)}x)")
        
        return "\n".join(lines)
    except Exception as e:
        return f"[-] Error retrieving open loops: {e}"


@mcp.tool()
def ulm_diagnose(deep: bool = False) -> str:
    """Runs a full, read-only diagnostic and integrity audit on the ULM (Universal Local Memory) database.
    
    Checks SQLite physical health (quick_check/integrity_check), WAL checkpoint status,
    fragmentation, foreign key constraints, FTS5 index integrity, and orphan records.
    
    Args:
        deep: If True, runs exhaustive PRAGMA integrity_check instead of quick_check.
    """
    try:
        db = get_db()
        diag = db.run_diagnostics(deep=deep)
        
        status_banner = f"=== ULM DIAGNOSTIC REPORT: {diag.get('status', 'UNKNOWN')} ==="
        lines = [
            status_banner,
            f"Database File: {diag.get('db_path')}",
            f"Execution Mode: {'Exhaustive (Deep)' if deep else 'Fast / Safe (Quick)'}",
            "",
            "--- [Physical Health & Storage] ---",
            f"- Total Allocated Size: {diag['physical_health'].get('total_size_mb', 0)} MB",
            f"- Unused Space (Freelist): {diag['physical_health'].get('unused_space_mb', 0)} MB ({diag['physical_health'].get('fragmentation_pct', 0)}% fragmentation)",
            f"- Journal Mode: {diag['physical_health'].get('journal_mode', 'unknown').upper()}",
            f"- SQLite B-Tree Check: {diag['physical_health'].get('sqlite_check')}",
            "",
            "--- [Schema & Key Integrity] ---",
            f"- Foreign Key Violations: {diag['schema_integrity'].get('foreign_key_violations', 0)}",
            "",
            "--- [Virtual Index (FTS5) Integrity] ---",
        ]
        for fts, fts_res in diag.get('fts_integrity', {}).items():
            lines.append(f"- {fts}: {fts_res}")
            
        lines.extend([
            "",
            "--- [Dataset Metrics & Anomaly Scan] ---",
            f"- Sessions: {diag['data_anomalies'].get('total_sessions', 0):,}",
            f"- Messages: {diag['data_anomalies'].get('total_messages', 0):,}",
            f"- Pinned/Active Facts: {diag['data_anomalies'].get('total_facts', 0):,}",
            f"- Orphaned Messages (Missing Session): {diag['data_anomalies'].get('orphaned_messages', 0)}",
            f"- Orphaned Embedding Cache Entries: {diag['data_anomalies'].get('orphaned_embeddings', 0):,}",
            f"- Facts with NULL Hash IDs: {diag['data_anomalies'].get('null_fact_hashes', 0)}",
        ])
        
        issues = diag.get('issues', [])
        if issues:
            lines.extend([
                "",
                "--- [Identified Issues & Recommendations] ---",
            ])
            for iss in issues:
                lines.append(f"[!] {iss}")
        else:
            lines.extend([
                "",
                "[+] Zero integrity flaws, b-tree corruptions, or foreign key errors detected.",
            ])
            
        return "\n".join(lines)
    except Exception as e:
        return f"[-] Diagnostics run failed with error: {e}"

@mcp.tool()
def ulm_resolve_thought(thought_id: int, status: str = "resolved") -> str:
    """Resolves or drops a parked thought / open loop once addressed or discarded.
    
    Args:
        thought_id: ID of the parked thought.
        status: New status ('resolved', 'dropped', 'parked'). Default 'resolved'.
    """
    try:
        db = get_db()
        success = db.resolve_thought(thought_id=thought_id, status=status)
        if success:
            return f"Successfully updated thought #{thought_id} status to '{status}'."
        else:
            return f"Thought #{thought_id} not found or not modified."
    except Exception as e:
        return f"[-] Error resolving thought: {e}"

if __name__ == "__main__":
    # Shield stdout from dirty prints/logs in any imported modules
    real_stdout_buffer = sys.stdout.buffer
    sys.stdout = sys.stderr

    import anyio
    from io import TextIOWrapper
    from mcp.server.stdio import stdio_server

    async def _run_clean_stdio():
        async with stdio_server(stdout=anyio.wrap_file(TextIOWrapper(real_stdout_buffer, encoding="utf-8", write_through=True))) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )

    anyio.run(_run_clean_stdio)
