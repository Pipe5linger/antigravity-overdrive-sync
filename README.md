# ⚡ Antigravity Overdrive Sync: Bespoke Local ETL Pipeline

A high-performance, lightweight **ETL** (*Extract, Transform, Load*) pipeline designed to automatically crawl, parse, deduplicate, and compile local Antigravity v2 chat histories into a structured, unified YAML state machine. 

Designed for developers using local LLMs, personal semantic memory engines, or anyone wanting a structured record of their pair-programming sessions.

## 🛠️ Architecture & Technical Highlights

*   **$O(1)$ Stream Processing**: Instead of reading massive, multi-gigabyte JSONL log files entirely into RAM—which leads to memory thrashing and eventually crashes the runtime—the sync engine processes logs line-by-line using a streaming generator.
*   **Atomic Writes**: Guaranteed write integrity. The system writes the synchronized state to a `.tmp` file first, then executes an atomic swap to overwrite the target YAML. If your PC loses power or crashes mid-sync, your database remains completely uncorrupted.
*   **Differential Mutators**: The engine checks file modification times (`mtime`) on local transcripts before executing the parser. If no changes are detected, the file is bypassed, keeping routine sync times near 0ms.
*   **Automatic XML Striping**: Cleans out raw UI markup (such as `<USER_REQUEST>` tags) on the fly, rendering raw dialogue logs optimized for immediate consumption by downstream LLM prompts or semantic indexers.
*   **Zero Hardcoding**: Dynamically resolves the user's home folder paths across multiple environments out-of-the-box.

## 📂 System Topology

```
[Local Antigravity Brain]
   │
   ├── (Crawl directory for logs/transcript.jsonl)
   ▼
[sync_engine.py] ───► (Line-by-line Stream Parser) ───► (Deduplication Layer)
   │
   ▼
[Atomic Swap Commit]
   │
   └──► [~\Desktop\Antigravity outputs\sync_state.yaml]
```

## 🚀 Quick Start

1.  **Clone the Repository** to your active workflow directory.
2.  **Install Dependencies**:
    ```bash
    pip install pyyaml
    ```
3.  **Run the Sync Engine**:
    ```bash
    python sync_engine.py
    ```
4.  **Automate via Task Scheduler**:
    Point Windows Task Scheduler to `sync.bat` to automate synchronization on a daily or hourly trigger. Ensure you set the "Start in" directory to your script folder.

## 🔒 Security & Privacy Notice
By default, the `.gitignore` included in this repository prevents your generated `sync_state.yaml` and temporary files from being committed. Always ensure you do not commit any files containing your actual personal chat transcripts.

