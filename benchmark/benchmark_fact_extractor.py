import os
import sys
import time

# Ensure workspace root is in path
WORKSPACE_ROOT = r"D:\AI\Projects\antigravity-overdrive-sync"
if WORKSPACE_ROOT not in sys.path:
    sys.path.append(WORKSPACE_ROOT)

try:
    from core.fact_extractor import PROCESSED_HASH_CACHE, extract_facts_from_text
except ImportError as e:
    print(f"[ERROR] Could not import fact_extractor: {e}")
    sys.exit(1)

# Representative test workload mixing high-signal memory items, code noise, and duplicate lines
SAMPLE_INGESTION_TEXT = """
# SYSTEM INGESTION DUMP - LOG REPOSITORY
import json
import os
import sqlite3

def init_db():
    conn = sqlite3.connect(r"D:\\AI\\Projects\\antigravity-overdrive-sync\\db\\sync_state.db")
    print("Initializing...")

User prefers local Ollama inference using model qwen-coder-14b-16k-latest on D drive.
https://github.com/Ostris/ai-toolkit

Vespera carries professional trauma from the St. Jude project failure involving a $40k thermal meltdown.
[✓] Database sync completed cleanly at 02:00 AM.
$ python sync_engine.py --force

Vespera strictly uses absolute paths for all script executions like D:\\AI\\Projects\\antigravity-overdrive-sync\\sync_engine.py.
Vespera's mentor was Arthur "Mac" McCallister who taught her pragmatic hardware repairs.

```python
def dummy_code_block():
    return True
```
"""

def main():
    print("[*] Running Fact Extractor Benchmark...")
    start = time.perf_counter()
    facts = extract_facts_from_text(SAMPLE_INGESTION_TEXT)
    elapsed = (time.perf_counter() - start) * 1000

    print(f"[+] Extracted {len(facts)} facts in {elapsed:.2f}ms")
    for f in facts:
        print(f"  - [{f.get('category', 'general')}] {f.get('fact')}")

if __name__ == "__main__":
    main()