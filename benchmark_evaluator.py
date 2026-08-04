import time
import statistics
import random
from typing import List, Dict, Any

try:
    from core.profile_evaluator import ProfileEvaluator
    from core.fact_extractor import FactExtractor
except ImportError:
    print("[!] Ensure this script is placed in your project root alongside 'core/'.")
    exit(1)


def generate_mock_sessions(total: int = 50) -> List[Dict[str, Any]]:
    """
    Generates 50 mock sessions with varying lengths and signal density:
    - 60% Zero-Signal / Casual Chatter (Fast-Path test)
    - 25% Short High-Signal (<10KB, contains profile facts)
    - 15% Heavy High-Signal (>30KB, test context condensing)
    """
    sessions = []
    
    casual_phrases = [
        "Hey, how's it going?", "Can you fix this syntax error?", 
        "Thanks, that worked!", "What's the weather today?",
        "npm run build failed with exit code 1", "git commit -m 'wip'"
    ]
    
    profile_facts = [
        "My name is Alex and I live in Seattle.",
        "I prefer working with Python, FastAPI, and Postgres.",
        "Never use spaces for indentation, always use 4 spaces.",
        "I am currently building an AI agent daemon system.",
        "Please remember that my server API runs on port 8080."
    ]

    for i in range(1, total + 1):
        rand_val = random.random()
        
        if rand_val < 0.60:
            # Type A: Zero Signal (~500 chars)
            dialogue = "\n".join([random.choice(casual_phrases) for _ in range(15)])
            category = "Zero-Signal"
        elif rand_val < 0.85:
            # Type B: Small High-Signal (<10KB)
            dialogue = "\n".join([random.choice(casual_phrases) for _ in range(20)])
            dialogue += f"\nUser: {random.choice(profile_facts)}\n"
            dialogue += "\n".join([random.choice(casual_phrases) for _ in range(20)])
            category = "High-Signal (Small)"
        else:
            # Type C: Large High-Signal (~40KB context bloat)
            padding = "User: How do I implement this function?\nAssistant: Here is the code snippet...\n" * 400
            dialogue = f"{padding}\nUser: {random.choice(profile_facts)}\n{padding}"
            category = "High-Signal (Heavy >30KB)"
            
        sessions.append({
            "session_id": f"sess_{i:03d}",
            "dialogue": dialogue,
            "char_count": len(dialogue),
            "expected_category": category
        })
        
    return sessions


def run_benchmark():
    print("=" * 60)
    print(" STARTING PROFILE EVALUATOR BENCHMARK (50 SESSIONS)")
    print(" Target Model: qwen2.5:7b-instruct")
    print("=" * 60)
    
    sessions = generate_mock_sessions(50)
    
    # Target qwen2.5:7b-instruct explicitly if supported by ProfileEvaluator signature
    try:
        evaluator = ProfileEvaluator(model_target="qwen2.5:7b-instruct")
    except TypeError:
        evaluator = ProfileEvaluator()

    # Pre-flight check: ensure evaluation method exists
    eval_method = getattr(evaluator, 'evaluate_dialogue', None) or getattr(evaluator, 'evaluate_session', None)
    if not eval_method:
        print("[!] ERROR: ProfileEvaluator has neither 'evaluate_dialogue' nor 'evaluate_session' method!")
        return

    session_latencies = []
    fast_path_hits = 0
    llm_calls = 0
    errors = 0
    batch_latencies = []
    
    batch_size = 5
    num_batches = len(sessions) // batch_size
    
    start_total_time = time.perf_counter()

    for b in range(num_batches):
        batch = sessions[b * batch_size : (b + 1) * batch_size]
        print(f"\n[Batch {b + 1}/{num_batches}] Processing {len(batch)} sessions...")
        
        batch_start = time.perf_counter()
        
        for sess in batch:
            s_start = time.perf_counter()
            
            try:
                result = eval_method(sess["dialogue"], session_id=sess["session_id"])
            except Exception as e:
                result = None
                print(f"  - [{sess['session_id']}] EXCEPTION: {e}")
                errors += 1

            s_elapsed = time.perf_counter() - s_start
            session_latencies.append(s_elapsed)
            
            # Determine fast-path via payload status first, fallback to latency guard
            is_fast_path = False
            if isinstance(result, dict):
                is_fast_path = result.get("fast_path") or result.get("bypassed") or (s_elapsed < 0.05 and result.get("status") == "skipped")
            elif result is not None and s_elapsed < 0.05:
                is_fast_path = True

            if is_fast_path:
                fast_path_hits += 1
                status_str = f"Fast-Path ({s_elapsed*1000:.1f}ms)"
            else:
                llm_calls += 1
                status_str = f"LLM Evaluated ({s_elapsed:.2f}s)"
                
            print(f"  - [{sess['session_id']}] {sess['char_count']:>6} chars | {sess['expected_category']:<24} -> {status_str}")

        batch_elapsed = time.perf_counter() - batch_start
        batch_latencies.append(batch_elapsed)
        print(f"  Batch Total: {batch_elapsed:.2f}s {'(OK <= 5s)' if batch_elapsed <= 5.0 else ' SLOW (>5s)'}")

    total_elapsed = time.perf_counter() - start_total_time

    # --- REPORT SUMMARY ---
    print("\n" + "=" * 60)
    print(" BENCHMARK SUMMARY & METRICS")
    print("=" * 60)
    print(f"Total Sessions Processed:   50")
    print(f"Total Execution Time:        {total_elapsed:.2f} seconds")
    print(f"Fast-Path Bypasses (0 LLM): {fast_path_hits} ({fast_path_hits/50*100:.1f}%)")
    print(f"LLM Full Evaluations:       {llm_calls} ({llm_calls/50*100:.1f}%)")
    if errors > 0:
        print(f"Execution Errors:           {errors}")
    print("-" * 60)
    print(f"Avg Session Latency:        {statistics.mean(session_latencies):.3f}s")
    print(f"Max Session Latency:        {max(session_latencies):.2f}s")
    print(f"Avg Batch Latency (5 items):{statistics.mean(batch_latencies):.2f}s")
    print(f"Max Batch Latency:          {max(batch_latencies):.2f}s")
    print("=" * 60)

    if max(batch_latencies) <= 5.0:
        print("SUCCESS: All 5-session batches completed within the <5s UI responsiveness target!")
    else:
        print("WARNING: Some batches exceeded 5.0s. Consider lowering batch size to 3 or 4.")

if __name__ == "__main__":
    run_benchmark()