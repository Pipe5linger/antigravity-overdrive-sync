import time
import json
from core.fact_extractor import FactExtractor

def test_stress_extraction():
    # 1. Construct a complex payload
    # Mixed content: JSON config, repeated logs, tracebacks, code blocks, and 3 specific facts
    payload = """
    # User Profile Configuration
    {
        "user_id": "vespera_01",
        "theme": "dark-nebula",
        "notifications": true,
        "api_version": "v2.4.1"
    }
    
    [INFO] 2026-08-02 02:15:01 - Syncing state to database...
    [INFO] 2026-08-02 02:15:01 - Syncing state to database...
    [INFO] 2026-08-02 02:15:01 - Syncing state to database...
    
    Traceback (most recent call last):
      File "sync_engine.py", line 42, in <module>
        main()
      File "sync_engine.py", line 110, in main
        run_sync()
    RuntimeError: Unexpected connection timeout from Ollama server.
    
    ```python
    def sync_logic():
        # This is a helper function for the sync engine
        print("Syncing...")
        return True
    ```
    
    I always prefer using SQLite for local memory storage because of its portability.
    
    [DEBUG] Connection heartbeat: OK
    [DEBUG] Connection heartbeat: OK
    
    Vespera has a deep scar on her left shoulder from the Great Collapse.
    
    Please remember that I never use 14B models for raw fact extraction to save VRAM.
    
    import os
    import sys
    from core.database import DBManager
    
    C:\AI\Projects\antigravity-overdrive-sync\core\fact_extractor.py
    
    The project workflow must strictly follow the 3-tier pipeline logic.
    """

    extractor = FactExtractor()
    
    print("--- Starting Stress Test ---")
    start_time = time.time()
    facts = extractor.extract(payload)
    end_time = time.time()
    
    duration_ms = (end_time - start_time) * 1000
    
    print(f"Execution Time: {duration_ms:.2f} ms")
    print("\nTelemetry Breakdown:")
    print(f"  - Tier 1 (Dropped/Noise): {extractor.telemetry['tier1_dropped']}")
    print(f"  - Tier 2 (Cache Hits):    {extractor.telemetry['tier2_hits']}")
    print(f"  - Tier 3 (Extracted):    {extractor.telemetry['tier3_extracted']}")
    
    print("\nExtracted Facts:")
    print(json.dumps(facts, indent=2))

    # Verification
    expected_facts = [
        "SQLite for local memory storage",
        "scar on her left shoulder",
        "never use 14B models for raw fact extraction"
    ]
    
    found_count = 0
    full_text = " ".join([f['fact'].lower() for f in facts])
    for ef in expected_facts:
        if any(keyword.lower() in full_text for keyword in ef.split()):
            found_count += 1
            
    print(f"\nVerification: Found {found_count}/{len(expected_facts)} target facts.")
    
    if found_count < 1:
        print("\n[FAIL] No core facts were extracted.")
    else:
        print("\n[PASS] Fact extraction pipeline is functional.")

if __name__ == "__main__":
    test_stress_extraction()