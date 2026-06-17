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

## 📦 Getting Started

1. **Clone the repository** and navigate to the root directory.
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure your environment**: Create a `.env` file based on `.env.example` to provide your API keys and local Ollama model options.
4. **Run the Dashboard TUI**:
   ```bash
   python main.py tui
   ```
5. **Start the background Daemon**:
   ```bash
    python main.py daemon
    ```

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