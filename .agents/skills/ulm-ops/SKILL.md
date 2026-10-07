---
name: ulm-ops
description: Operating procedures, query strategies, and data maintenance for the Universal Local Memory (ULM) SQLite database, vector embeddings, and taboo protocol rules.
---

# Universal Local Memory (ULM) Operations Guide

## 1. Core Architecture Overview
The ULM engine maintains state in `db/sync_state.db` using SQLite with Write-Ahead Logging (`WAL`).

Key Tables:
* `facts`: Semantic memory items extracted from interactions (columns: `id`, `fact`, `category`, `confidence`, `project_tag`, `created_at`).
* `embeddings`: Dense vector representations (MiniLM 384-dim) linked to `fact_id`.
* `taboo_rules`: Operational failure patterns, regex triggers, and remediations.
* `developer_profile`: Behavioral observations, coding preferences, and developer metrics.
* `procedures`: Registered CLI and diagnostic playbooks.

---

## 2. FastMCP Memory Tools

### `ulm_recall(query, limit, category)`
* Performs a dual-layer hybrid search:
  * **Layer 1**: Semantic cosine vector distance over embedding vectors.
  * **Layer 2**: Full-Text Search (FTS5 BM25) across `facts` and `developer_profile`.
* Use when: Needing past context on architectural decisions, developer quirks, or historical code solutions.

### `ulm_pin_fact(fact, category, confidence, project_tag)`
* Inserts a permanent semantic fact and immediately calculates and saves its vector embedding.
* Categories: `technical`, `preference`, `architectural`, `system_rule`.

### `ulm_check_taboo(command_or_code)`
* Scans candidate shell commands or code snippets against active regex rules in `taboo_rules`.
* Must be called before executing risky shell operations or complex multi-step pipelines.

### `ulm_recall_script(query, limit, category, include_code)`
* Recalls previously generated scratch scripts and utilities from the ULM Script Vault (`script_vault` / `script_vault_fts`) to eliminate redundant code generation and token waste.
* Categories: `database`, `vram_gpu`, `comfyui`, `telemetry_logs`, `benchmark`, `utility`.

### `ulm_inspect_db(table, limit, schema)`
* Inspects table schemas, column types, row counts, and sample records directly without shell scripts.

---

## 3. Best Practices & Safety Constraints
* **Concurrency**: Always ensure SQLite connects with `timeout=5.0` or issues `PRAGMA busy_timeout = 5000;`.
* **WAL Hygiene**: Run `ulm_vacuum_db()` periodically to checkpoint the WAL and reclaim fragmented disk space.
* **Orphan Cleanup**: Never leave orphaned rows in `embeddings` where `fact_id` no longer exists.
