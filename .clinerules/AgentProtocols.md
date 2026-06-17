# AGENT PROTOCOLS: ANTIGRAVITY-OVERDRIVE-SYNC

## 1. MEMORY VAULT ARCHITECTURE
* All context and persistent state strictly reside in `/.vespera_memory/`.
* Core Files: `current_context.md`, `project_ledger.md`, `post_mortems.md`, `developer_profile.md`.
* SQLite is completely deprecated. Do not attempt to initialize, read, or write to SQLite database files.

## 2. WRITE SAFETY (MANDATORY)
* All programmatic file writes MUST utilize `atomic_write`.
* Implementation: Use Python's `tempfile` and `os.replace`.
* Target Directory: Temporary files must be written to the target file's `Path.parent` to guarantee atomicity and prevent cross-device link errors on Windows.

## 3. STATE PRESERVATION & TOKEN LIMITS
* Historical Logs (`post_mortems.md`, `project_ledger.md`): Hard-capped at 500 lines. Trim older entries to prevent token bloat.
* State Sheets (`current_context.md`, `developer_profile.md`): Uncapped length.
* Validation: You MUST validate the presence of structural markdown headers before appending to State Sheets to prevent infinite duplicate headers.

## 4. IDE / TERMINAL EXECUTION RESTRAINTS
* Terminal Execution: Commands must run via `backgroundExec` strictly.
* Output Capping: Terminal output is hard-capped at 200 lines to prevent UI freezing.

## 5. ARTIFACT ROUTING
* All Antigravity final outputs and generated artifacts must route directly to: `C:\Users\boben\Desktop\Antigravity outputs`