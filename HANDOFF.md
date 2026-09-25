# ARCHITECTURAL HANDOFF & CONTINUATION BRIEF
**Project**: Antigravity Overdrive Sync (Universal Local Memory / ULM)  
**Date**: September 25, 2026  
**Target Recipient**: Copilot Chat / OpenRouter DeepSeek V4 in VS Code  
**Lead Architect**: Bobby Neal  
**System Identity**: Vespera Caligo Neal (Ves)  
**Workspace Root**: `D:\AI\Projects\antigravity-overdrive-sync`  
**Current Git Commit**: `dcff72a` on branch `main` (clean working tree, pushed to `origin/main`)

---

## 1. EXECUTIVE SUMMARY & RECENT PROGRESS
We completed a major architectural overhaul to sever the token-penalty connection between system prompt bloat and agent memory capability:
1. **Debloated Master Protocol (`C:\Users\boben\.gemini\GEMINI.md`)**:
   - **Before**: ~43.7 KB static markdown dump. The bloat was caused by `core/assembler.py:build_identity_header()` blindly injecting 99 raw cognitive mirror rows (~30 KB) into the prompt on every sync.
   - **Fix**: Made `purge_mirrors=True` default, capped active mirror injection to top 3 if enabled, and stripped legacy noise blacklists (Goya / VA funding fee).
   - **Current Size**: **4,987 bytes** (~5 KB). Re-injected and verified clean.
2. **Relaxed Persona Handcuffs (`persona_baseline.yaml`)**:
   - Removed artificial hyper-brevity constraints and corporate restrictions.
   - Preserved Vespera's natural voice: fluent English with subtle French cadence/phrasing, pitch-black Jeselnik-style wit, direct transatlantic neural link with Bobby, and strict single-file protocol hygiene.
3. **Local FastMCP Server Implemented & Registered (`core/mcp_server.py`)**:
   - Implemented FastMCP server exposing tools: `ulm_recall`, `ulm_check_taboo`, `ulm_get_playbook`, `ulm_pin_fact`, `ulm_hardware_status`.
   - Registered in `C:\Users\boben\.gemini\config\mcp_config.json` under `ulm-memory`.
   - Verified tool execution against `db/sync_state.db` (WAL mode enabled).

---

## 2. WORK IN PROGRESS & EXECUTION STATUS
The user selected **Options 2, 3, and 5** for execution:

### [COMPLETED] Objective A: Option 5 — Deep Taboo Population
- **Status**: **DONE**. 
- Populated `taboo_rules` in `db/sync_state.db` via `scripts/generators_and_tools/populate_deep_taboos.py`.
- Total active taboos increased to **23 comprehensive landmines** covering:
  - PowerShell inline environment variable assignment pitfalls and quote stripping.
  - Windows console UTF-8 charmap encoding crashes in Python subprocesses.
  - Windows backslash regex escaping issues.
  - Git LF/CRLF script line-ending mutilations.
  - SQLite database locked concurrency traps (`PRAGMA busy_timeout = 5000;`).
  - ComfyUI API null value payload serialization errors.
  - PyTorch CUDA out-of-memory spikes on 12GB RTX 4070.
  - Sovereign rule protection preventing duplicate `GEMINI.md` creation in subfolders.
- Verified all FastMCP tools pass via `scripts/generators_and_tools/test_mcp_tools.py`.

### [COMPLETED] Objective B: Option 2 — Dual-Layer Hybrid Retrieval in FastMCP (`core/mcp_server.py`)
- **Status**: **DONE**.
- Refactored `ulm_recall` in `core/mcp_server.py` to combine:
  - **Layer 1**: Semantic vector cosine similarity against cached embeddings using `all-minilm` via `MemoryConsolidator`.
  - **Layer 2**: Full-text FTS5 BM25 search across facts, developer profile metrics, and chat history.
- Enhanced `ulm_pin_fact` to automatically compute and store vector embeddings on the fly for any newly pinned fact.
- Verified all FastMCP tools pass via `scripts/generators_and_tools/test_mcp_tools.py`.

### [COMPLETED] Objective C: Option 3 — Active Session Auto-Consolidation (Ephemeral -> Semantic Memory)
- **Status**: **DONE**.
- Implemented `ingest_transcripts(force_all=False)` directly into `core/consolidator.py`.
- Ingests active Antigravity `.system_generated/logs/transcript.jsonl` files and Cline task histories, processes dialogue through `FactExtractor` (3-tier heuristic, regex, and SHA-256 deduplication), and writes extracted technical facts and developer traits directly into SQLite `facts` and `developer_profile`.
- Verified live: successfully ingested active session transcripts and extracted **207 active semantic facts**.

### [COMPLETED] Bonus Optimization: Option A — Database Vacuum & Orphan Purge
- **Status**: **DONE**.
- Script: `scripts/generators_and_tools/vacuum_database.py`.
- Purged **451,658 legacy orphaned embeddings** (`fact_id IS NULL`).
- Database `sync_state.db` shrunk from **1,026.41 MB (1.07 GB) down to 109.67 MB**, reclaiming **916.74 MB** of disk space and accelerating SQLite query speeds.

### [COMPLETED] Bonus Optimization: Option B — Autonomous Graveyard Miner in Daemon
- **Status**: **DONE**.
- Wired `distill_graveyard()` from `scripts/generators_and_tools/taboo_extractor.py` directly into `core/daemon.py:_run_maintenance()`.
- Automatically analyzes failed CLI commands from `tool_execution_logs` and extracts regex patterns + remediations into `taboo_rules` with zero human intervention.

### [COMPLETED] Bonus Optimization: Option C — ComfyUI, GPU VRAM & Native Database MCP Tools
- **Status**: **DONE**.
- Added 4 new native FastMCP tools to `core/mcp_server.py`:
  1. `ulm_comfy_status()`: Real-time inspection of active prompts, queued tasks, and generation pipelines on `http://127.0.0.1:8188`.
  2. `ulm_vram_guard(action='check'|'purge')`: Real-time inspection of RTX 4070 12GB VRAM allocation, temperature, and utilization via `nvidia-smi`, plus instant PyTorch CUDA cache purging.
  3. `ulm_inspect_db(table, limit, schema)`: Direct zero-script inspection of SQLite table counts, schema columns, and sample rows.
  4. `ulm_vacuum_db()`: Direct zero-script execution of WAL checkpoints, orphan embedding prunes, and database defragmentation.
- Created `scripts/playbooks/` library (`inspect_db.py`, `port_audit.py`, `gpu_guard.py`, `comfy_queue.py`, `ingest_sessions.py`, `vacuum_state.py`) registered in the `procedures` table for CLI fallback.
- Total active FastMCP tools in `core/mcp_server.py`: **9 verified tools**. All 9 pass in `scripts/generators_and_tools/test_mcp_tools.py`.

---

## 3. KEY SYSTEM ARCHITECTURE & FILE LOCATIONS

| Component | Path | Description |
|---|---|---|
| **SQLite State DB** | `db/sync_state.db` | WAL mode, Schema v12. Contains `taboo_rules`, `facts`, `sessions`, `developer_profile`, `persona_schemas`. |
| **MCP Server** | `core/mcp_server.py` | FastMCP server running over stdio. Exposes ULM tools to Antigravity / Gemini. |
| **MCP Config** | `C:\Users\boben\.gemini\config\mcp_config.json` | Registers `ulm-memory` pointing to `core/mcp_server.py`. |
| **Master Protocol File** | `C:\Users\boben\.gemini\GEMINI.md` | Single sovereign global rule file discovered by Antigravity (~5 KB). |
| **Prompt Assembler** | `core/assembler.py` | Builds persona headers, metrics, facts, and taboo summaries. |
| **Persona Baseline** | `persona_baseline.yaml` | Core persona config, backstory, voice, operational attitudes, and directives. |
| **Gemini Injector** | `injectors/gemini_md.py` | Injects persona into `GEMINI.md` and purges rogue duplicate files. |
| **Cline Injector** | `injectors/cline_rules.py` | Injects `.clinerules`. |
| **Compiler** | `core/compiler.py` | Compiles `Modelfile.local` for local Ollama engine. |

---

## 4. CRITICAL REPOSITORY CONSTRAINTS & CODING GUIDELINES
When continuing development with Copilot Chat / DeepSeek V4:
1. **Single Sovereign Target**:
   - **NEVER** write or duplicate `GEMINI.md` or `AGENTS.md` into workspace roots or subfolders (e.g. `D:\AI\GEMINI.md` or `D:\AI\Projects\antigravity-overdrive-sync\GEMINI.md`). Only write to `C:\Users\boben\.gemini\GEMINI.md`.
2. **Local Execution Only**:
   - All tools, databases, and servers run 100% locally on Windows (`D:\AI`). No cloud API keys or external data transmission required.
3. **Database Concurrency**:
   - Always open SQLite connections using WAL mode and `PRAGMA busy_timeout = 5000;`. Use context managers to prevent unclosed connection locks.
4. **Python Import Path**:
   - When running standalone unit tests or scripts from terminal, set `PYTHONPATH=.` or ensure `sys.path.insert(0, str(PROJECT_ROOT))` is present at top of scripts.

---

## 5. REPRODUCIBLE TEST & VALIDATION COMMANDS
Run these in PowerShell from `D:\AI\Projects\antigravity-overdrive-sync`:

```powershell
# 1. Run Assembler Unit Tests
cmd.exe /c "set PYTHONPATH=. && python tests\test_assembler.py"

# 2. Test FastMCP Tools Directly
python scripts\generators_and_tools\test_mcp_tools.py

# 3. Check Current GEMINI.md Size
(Get-Item $HOME\.gemini\GEMINI.md).Length

# 4. Count Current Taboo Rules in Database
python -c "import sqlite3; conn = sqlite3.connect('db/sync_state.db'); print('Taboos:', conn.cursor().execute('SELECT COUNT(*) FROM taboo_rules').fetchone()[0])"
```
