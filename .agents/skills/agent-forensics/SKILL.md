---
name: agent-forensics
description: Automated post-mortem analysis of agent conversation transcripts, failure loops, Python tracebacks, and tool execution crashes, with automated pytest regression synthesis.
---

# AGENT-FORENSICS :: Automated Post-Mortem & Error Triaging Skill

## 1. Scope & Objective
This skill provides automated diagnostic procedures for isolating, triaging, and remediating agentic failures across:
* **Antigravity Transcripts**: `C:\Users\boben\.gemini\antigravity\brain\<conversation-id>\.system_generated\logs\transcript.jsonl`
* **Agent Error Harvester**: `d:\AI\Projects\agent-error-harvester`
* **Subprocess & Shell Failures**: PowerShell exit codes, Python tracebacks, and encoding collisions.

---

## 2. Ingestion & Triage Protocol

### Step 1: Locate the Diagnostic Target
To locate the active or historical conversation log:
1. Active session logs reside in:
   `C:\Users\boben\.gemini\antigravity\brain\<active-conversation-id>\.system_generated\logs\transcript.jsonl`
2. Fallback to `transcript_full.jsonl` only if `truncated_fields` contains the error payload.

### Step 2: Parse Failure Steps
Filter lines where `status == "ERROR"` or inspect `PLANNER_RESPONSE` blocks containing Python tracebacks or nonzero shell exit codes:
```python
import json

def extract_errors(transcript_path):
    errors = []
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("status") == "ERROR" or "Traceback" in str(entry.get("content", "")):
                errors.append({
                    "step_index": entry.get("step_index"),
                    "type": entry.get("type"),
                    "content": entry.get("content")
                })
    return errors
```

---

## 3. Failure Mode Taxonomy & Immediate Remediation

| Failure Mode | Root Cause Signature | Immediate Remediation |
| :--- | :--- | :--- |
| **Windows Charmap Crash** | `'charmap' codec can't decode byte 0x...` | Enforce UTF-8 in Python subprocess: `$env:PYTHONIOENCODING='utf-8'` and `open(f, encoding='utf-8')`. |
| **SQLite Lock Contention** | `sqlite3.OperationalError: database is locked` | Enable WAL mode (`PRAGMA journal_mode=WAL;`) and enforce `PRAGMA busy_timeout = 5000;`. |
| **CUDA VRAM Blowout** | `torch.cuda.OutOfMemoryError: CUDA out of memory` | Call `ulm_vram_guard(action='purge')`, flush cache, downscale latent batch or offload text encoder. |
| **Agent Hallucination Loop** | Agent calls same failing tool 3+ times with identical args | Interrupt loop, switch strategy, or request user clarification. |
| **PowerShell Syntax Leak** | `VAR=val : The term 'VAR=val' is not recognized` | Convert Linux inline environment syntax to `$env:VAR='val'; <cmd>`. |

---

## 4. Regression Synthesis (PyTest Harness)

For every triaged bug, synthesize a minimal reproducible unit test under `tests/` before declaring resolution:

```python
import pytest

def test_regression_case():
    """Verify that specific failure pattern does not reoccur under edge input."""
    # 1. Arrange failure conditions
    # 2. Act
    # 3. Assert correct handling or graceful error
    assert True
```

---

## 5. Dossier Reporting Format

When reporting findings to Bobby or subagents, use this compact format:
```markdown
### Forensic Summary: [Error Name]
* **Failure Point**: `step_index` or file + line number.
* **Root Cause**: Specific mechanism (e.g. unbuffered binary pipe, missing lock timeout).
* **Fix Applied**: Atomic diff in [target_file.py](file:///path/to/target_file.py).
* **Verification**: Command and test result confirming fix.
```
