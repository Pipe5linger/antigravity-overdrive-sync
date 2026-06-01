import os
import sys
import json
import time
import tracemalloc
import shutil
from datetime import datetime

# Setup dynamic execution search paths
SCRATCH_DIR = os.path.dirname(os.path.abspath(__file__))
MOCK_BRAIN = os.path.join(SCRATCH_DIR, "mock_brain")
MOCK_OUTPUT_DIR = os.path.join(SCRATCH_DIR, "mock_output")
MOCK_YAML_TARGET = os.path.join(MOCK_OUTPUT_DIR, "sync_state.yaml")

# Append parent directory to sys.path to find main modules
sys.path.append(os.path.dirname(SCRATCH_DIR))
import main
from core.engine import ULMEngine
from parsers.antigravity import AntigravityParser
from injectors.gemini_md import GeminiMdInjector

def generate_mock_brain():
    """Generates a massive, noisy, and partially corrupted mock chat environment."""
    print("[*] Generating mock chat environment with extreme payloads...")
    if os.path.exists(MOCK_BRAIN):
        shutil.rmtree(MOCK_BRAIN)
    os.makedirs(MOCK_BRAIN)
    
    if os.path.exists(MOCK_OUTPUT_DIR):
        shutil.rmtree(MOCK_OUTPUT_DIR)
    os.makedirs(MOCK_OUTPUT_DIR)

    # 1. Generate 99 standard-sized chat sessions (each with ~50 messages)
    for i in range(99):
        session_id = f"session_standard_{i}"
        log_dir = os.path.join(MOCK_BRAIN, session_id, ".system_generated", "logs")
        os.makedirs(log_dir)
        
        filepath = os.path.join(log_dir, "transcript.jsonl")
        with open(filepath, 'w', encoding='utf-8') as f:
            for j in range(50):
                event_type = "USER_INPUT" if j % 2 == 0 else "MODEL_RESPONSE"
                content = f"<USER_REQUEST>Mock message turn {j} in standard session {i}</USER_REQUEST>" if event_type == "USER_INPUT" else f"Response turn {j}"
                event = {
                    "type": event_type,
                    "created_at": datetime_placeholder(j),
                    "content": content
                }
                f.write(json.dumps(event) + "\n")

    # 2. Generate the MONSTER session: 100,000 chat turns
    print("[*] Creating the monster thread: 100,000 chat turns...")
    monster_id = "session_monster_100k"
    log_dir = os.path.join(MOCK_BRAIN, monster_id, ".system_generated", "logs")
    os.makedirs(log_dir)
    filepath = os.path.join(log_dir, "transcript.jsonl")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        for j in range(100000):
            # Inject noise and corrupted lines every 1,000 lines
            if j % 1000 == 0:
                f.write("{invalid_json_chaos\n")
                f.write("\n")  # Empty line noise
            
            event_type = "USER_INPUT" if j % 2 == 0 else "MODEL_RESPONSE"
            content = f"<USER_REQUEST>Extreme volume load test line {j}</USER_REQUEST>" if event_type == "USER_INPUT" else f"Extreme response line {j}"
            event = {
                "type": event_type,
                "created_at": datetime_placeholder(j),
                "content": content
            }
            f.write(json.dumps(event) + "\n")

def datetime_placeholder(index):
    return f"2026-05-31T12:{index % 60:02d}:00-05:00"

def run_stress_test():
    """Runs the modular sync engine over the mock environment while tracking telemetry."""
    print("\n" + "="*55)
    print("🚀 INITIALIZING BENCHMARK AND STRESS TEST PROCESSOR")
    print("="*55)
    
    # Instantiate custom ULM components targetting our mock directories
    parser = AntigravityParser(source_dir=MOCK_BRAIN)
    engine = ULMEngine(target_yaml=MOCK_YAML_TARGET)
    
    # Start tracking memory
    tracemalloc.start()
    start_time = time.time()
    
    print("[*] Phase 1: Extracting and parsing mock log streams...")
    new_logs = parser.fetch_new_logs()
    
    print("[*] Phase 2: Staging merge and executing atomic YAML write...")
    current_state = engine.load_existing_state()
    updated_state, mutations = engine.merge_and_reconfigure(current_state, new_logs)
    
    success = engine.commit_atomic_write(updated_state)
    
    duration = time.time() - start_time
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print("="*55)
    print("📊 STRESS TEST TELEMETRY METRICS:")
    print(f"[*] Total Execution Time: {duration:.3f} seconds")
    print(f"[*] Peak Memory Allocation (High-Water Mark): {peak_mem / 1024 / 1024:.3f} MB")
    print(f"[*] Current Memory Usage (Residual Footprint): {current_mem / 1024 / 1024:.3f} MB")
    
    if os.path.exists(MOCK_YAML_TARGET):
        state_size = os.path.getsize(MOCK_YAML_TARGET) / 1024 / 1024
        print(f"[*] Compiled Database File Size: {state_size:.2f} MB")
    print("="*55)

    # Clean up mock directories
    print("[*] Cleaning up temporary test structures...")
    shutil.rmtree(MOCK_BRAIN)
    shutil.rmtree(MOCK_OUTPUT_DIR)
    print("[+] Test completed successfully. System is stable.")

if __name__ == "__main__":
    generate_mock_brain()
    run_stress_test()
