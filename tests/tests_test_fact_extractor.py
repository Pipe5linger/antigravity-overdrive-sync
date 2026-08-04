# tests/test_fact_extractor.py
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from core.fact_extractor import FactExtractor  # Adjust import based on your exact class/function name

# Heavy noise + embedded signal payload
STRESS_TEST_PAYLOAD = """
[2026-08-02 02:14:01] INFO: Initializing sync engine daemon on D:\\AI\\Projects\\antigravity-overdrive-sync
[2026-08-02 02:14:02] DEBUG: Loading config file from D:\\AI\\Projects\\antigravity-overdrive-sync\\config.json
[2026-08-02 02:14:02] DEBUG: Raw config payload:
```json
{
    "db_path": "sync_state.db",
    "timeout_ms": 2000,
    "wal_mode": true,
    "model_target": "qwen-coder-14b-16k-latest",
    "vram_limit_gb": 12
}