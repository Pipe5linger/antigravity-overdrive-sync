# Antigravity Overdrive Sync (Universal Local Memory)

Welcome! This is a local, multi-threaded pipeline built to grab AI chat histories, process them, and compile structured milestone summaries and memory rules straight into your local markdown systems (like `.clinerules` or `GEMINI.md`). It keeps a persistent, queryable state record inside a local SQLite database and features a clean terminal user interface (TUI).

---

## 🚀 Key Features

* **Relational Memory Storage**: Migrated from flat YAML files to an optimized, transaction-safe SQLite database running in WAL (Write-Ahead Logging) mode.
* **TUI Dashboard Control**: A terminal user interface (`rich`-powered) to monitor database metrics, sync logs on demand, update preferences, and read your behavioral telemetry in real-time.
* **Background Daemon Poller**: A folder-watcher script (`core/daemon.py`) that monitors workspace transcripts and runs synchronization cycles automatically in the background.
* **Memory Consolidation (Conflict Resolution)**: Uses a local LLM or Gemini to batch-evaluate facts periodically, pruning contradictory information, merging redundancies, and maintaining "fact aging."
* **Context-Aware Workspace Tagging**: Automatically extracts project tags based on execution paths (`Cwd`) from your logs, prioritizing rules and memories depending on the active workspace you are coding in.
* **Hierarchical Memory Cores**: Constructs context-rich system prompts divided into distinct tiers (Tier 1 Episodic/Temporal, Tier 2 Cognitive/Behavioral, Tier 3 Semantic/Facts) to keep active contexts clean and within tight token limits.

---

## 📖 Step-by-Step Setup & User Guide

Whether you want to run ULM as a background memory daemon or use the interactive console dashboard, here is how to get running in under 2 minutes:

### 1. Requirements & Prerequisites
- **Python 3.10+** (Python 3.11 recommended)
- **Git**
- Optional: **Ollama** or **KoboldCpp** (for local offline LLM summarization) or a **Google Gemini API Key** (for cloud summarization).

### 2. Installation
```bash
# 1. Clone the repository
git clone https://github.com/Pipe5linger/antigravity-overdrive-sync.git
cd antigravity-overdrive-sync

# 2. Create and activate a virtual environment (recommended)
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

### 3. Environment Setup (`.env`)
Create a `.env` file in the root directory:
```env
# Optional: Set Gemini API key for cloud summarization
GEMINI_API_KEY="your-api-key-here"

# Optional: Set local LLM model names for Ollama/Kobold
LLM_MODEL="qwen2.5-coder-14b-32k-Vespera:latest"
VECTOR_MODEL="nomic-embed-text:latest"
```

### 4. Running ULM

#### Option A: Manual One-Shot Sync
Scans all active workspace transcripts, updates the SQLite database, and compiles dynamic system prompts (`GEMINI.md` / `.clinerules`):
```bash
python main.py sync
```

#### Option B: Terminal Dashboard TUI
Launches the interactive `rich`-powered console dashboard:
```bash
python main.py tui
```

#### Option C: Background Daemon Poller (Automated)
Runs the lightweight poller loop to automatically sync memories whenever transcript files change in your workspace:
```bash
python main.py daemon
```
*Tip for Windows users*: You can run the daemon silently in the background without keeping a console window open using `sync_silent.vbs` or `daemon_silent.vbs`.

---

## 🛠️ How It Works (Architecture Overview)

```text
[ Transcript Logs ] ──(Stream Parser)──> [ SQLite WAL DB ] ──(Consolidator)──> [ Tier 1-4 Cores ] ──> [ GEMINI.md ]
```

1. **Ingest Phase**: Streams JSONL transcript logs from Roo-Cline / Antigravity workspace paths with O(1) memory overhead.
2. **Indexing Phase**: Stores raw session messages, topics, and timestamps into `sync_state.db` using transactional SQLite WAL mode.
3. **Consolidation Phase**: Fact extractor prunes duplicate facts, handles conflict resolution, and applies "fact aging."
4. **Assembly Phase**: Dynamic prompt assembler generates hierarchical prompt files (`GEMINI.md`, `.clinerules`, or Ollama `Modelfile`) categorized into Tier 1 (Episodic), Tier 2 (Behavioral Profile), Tier 3 (Facts), and Tier 4 (Workstation Map).

---

## 🧪 Verification & Testing

To ensure code integrity and prevent regressions, you can run the test suite in two ways:

### 1. Native Testing
If you have your virtual environment activated locally:
```bash
python -m unittest discover tests
```

### 2. Sterile Container Testing (Docker)
If you want to run tests in an isolated, clean-room environment to ensure all dependencies are correctly defined (without polluting your local host):
```bash
docker run --rm -v "${PWD}:/workspace" -w /workspace python:3.11-slim bash -c "pip install -r requirements.txt && python -m unittest discover tests"
```

---

## ⚠️ Fair Warning: I Am Learning As I Go!

Let's be completely honest: **I don't entirely know what the hell I am doing yet.** I only started diving into Python, databases, and Git very recently. This project is my hands-on sandbox for learning how to build local AI data pipelines. Because of that:
- The code is probably messy, unconventional, or violates some standard Python paradigms.
- I am figuring out multi-threading, database locks, and API handling on the fly.
- There are definitely things here that can be optimized, refactored, or completely rewritten.

I am not trying to pretend this is a polished enterprise application—it's a raw, functional tool running on my personal workstation iron that I am actively trying to harden.

---

## 🤝 I Genuinely Want Your Help & Critiques!

If you are an experienced developer, a Python wizard, or just someone who likes optimizing data pipelines, **please tear this code apart.** I am incredibly open to constructive criticism, brutal code reviews, and mentorship.

I would love your help, suggestions, or pull requests regarding:
1. **Code Architecture & Cleanup:** Better ways to structure my classes, handle imports, or separate concerns.
2. **Dynamic Rate Limiting:** Asynchronous token-bucket rate limiters.
3. **Database Performance:** SQLite optimization tips under high-concurrency workloads.
4. **Async Migration:** Moving the entire network/file pipeline from synchronous threads over to a clean async architecture.

---

## 🚀 How to Look Around

Because this repository enforces a strict security perimeter via `.gitignore`, private database files (`sync_state.db`), and personal transcripts are completely excluded. 

You are looking at a clean, sterile engine blueprint:
* `main.py`: The central execution entry point.
* `core/database.py`: Manages the SQLite schema, migrations, and transactional inserts.
* `core/consolidator.py`: Resolves memory conflicts, redundant facts, and aging.
* `core/assembler.py`: Compiles the dynamic system prompt divided into memory hierarchies.
* `tui/dashboard.py`: Renders the terminal dashboard and controls active sync flows.

### Getting Involved

If you spot a bug, see a line of code that makes you cringe, or have an idea on how to make this better:
- Open an **Issue** with your feedback or critique.
- Drop a thought in the **Discussions** tab.
- Submit a **Pull Request**—I would love to study your code changes!

Thank you for stopping by and helping a self-taught dev build cleaner iron!