# Universal Local Memory (ULM)

A lightweight, persistent memory layer for AI coding assistants.

---

## The Problem

Most AI coding assistants operate between two frustrating extremes:

1. **Session Amnesia:** Opening a new chat resets the assistant to zero. You find yourself repeatedly re-explaining your stack, hardware constraints, file paths, and personal preferences.
2. **Context Bloat & Token Degradation:** Keeping a single sprawling conversation open causes the entire transcript to be re-sent with every prompt. This inflates input costs, exhausts context windows, slows down generation, and dilutes model attention.

**ULM provides a middle ground.** It runs locally in the background, extracts meaningful facts and recurring failure patterns from your session logs, and injects a compact, structured memory block into your workspace rules (`.clinerules`, `GEMINI.md`, or local Modelfiles).

---

## Core Capabilities

* **Bounded Context Injection:** Keeps active prompt overhead capped (typically under 800 tokens) using structured memory tiers rather than dumping raw transcripts.
* **Negative Constraint Tracking (Error Graveyard):** Records terminal execution failures and tool tracebacks into an indexed list of taboos, actively preventing the model from re-attempting known broken commands.
* **Multi-Environment Synchronization:** Maintains consistency across Antigravity, Cline, Copilot, and local Ollama models from a single local database.
* **Local & Private by Design:** All sessions, facts, and embeddings reside in a local SQLite database on your machine. No telemetry or proprietary code is shared with external services.
* **Automated Background Ingestion:** Monitors workspace logs and updates your instruction files automatically as you code.

---

## Quickstart

### Prerequisites
* **Python 3.10+** (Python 3.11 recommended)
* **Git**

### Installation
```bash
# 1. Clone the repository
git clone https://github.com/Pipe5linger/antigravity-overdrive-sync.git
cd antigravity-overdrive-sync

# 2. Set up a virtual environment
python -m venv venv

# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

### Configuration (Optional)
If you want cloud-assisted summarization or local model routing, copy `.env.example` to `.env`:
```env
# Optional: Google Gemini API key for cloud summarization
GEMINI_API_KEY="your-api-key-here"

# Optional: Local model identifier for Ollama
LLM_MODEL="qwen2.5-coder:latest"
```

---

## Running ULM

### 1. Manual One-Shot Sync
Scans recent workspace logs, extracts new facts, and updates your prompt instruction files:
```bash
python main.py sync
```

### 2. Terminal Dashboard (TUI)
Launches an interactive, `rich`-powered console interface to monitor database tables, view captured taboos, and inspect token metrics:
```bash
python main.py tui
```

### 3. Background Daemon
Runs a lightweight file watcher that synchronizes memories whenever transcripts update:
```bash
python main.py daemon
```
*Windows users can also use `sync_silent.vbs` or `daemon_silent.vbs` to run silently in the background without keeping a console window open.*

---

## Integrated Verification & Swarm Audits

ULM includes automated subagent playbooks to verify system health and enforce code standards:

```bash
# Run all diagnostic checks in parallel
python scripts/playbooks/swarm_orchestrator.py --all --parallel
```

Included audits:
* **Security Auditor (`sec_auditor.py`):** Scans for exposed API keys, unparameterized SQL statements, and `.gitignore` compliance.
* **Test Harness Engineer (`test_engineer.py`):** Runs the pytest suite, validates SQLite WAL concurrency under load, and enforces prompt token budget ceilings.
* **Migration Architect (`migration_architect.py`):** Audits database schema integrity, verifies FTS5 virtual table synchronization, and ensures persona schemas remain deduplicated.

---

## Architecture Overview

```text
[ Transcripts: Antigravity / Cline / Gemini ]
                     │
                     ▼
           (Streaming Parser)
                     │
                     ▼
        [ SQLite WAL Database ]
   (Facts, Taboo Rules, Schema Profiles)
                     │
                     ▼
        (Compact Prompt Assembler)
                     │
                     ▼
    [ .clinerules / GEMINI.md / Modelfiles ]
```

1. **Ingest:** Streams raw JSONL and markdown transcripts from your coding environments.
2. **Normalize & Store:** Extracts structured facts, user preferences, and execution failures into `sync_state.db`.
3. **Prune & Deduplicate:** Merges redundant information and retires stale error taboos.
4. **Compile:** Generates a deterministic, bounded prompt block that equips the assistant with persistent context without token bloat.

---

## Project Status & Community Feedback

**Full disclosure:** I am a self-taught developer building tools to solve real problems encountered during daily paired programming. 

While this system is actively used on my primary workstation and hardened against daily workflows:
* The codebase is evolving rapidly as I learn better design patterns.
* Concurrency handling, async pipelines, and database tuning are ongoing learning areas.
* Constructive critiques, architectural feedback, and pull requests from experienced developers are genuinely welcome.

If you spot something that could be written more cleanly, safely, or efficiently, please feel free to open an **Issue** or submit a **Pull Request**.

Thanks for exploring the project!