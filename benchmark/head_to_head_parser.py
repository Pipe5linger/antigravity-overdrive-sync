import os
import sys
import time
import subprocess
import json
from datetime import datetime

# Enforce UTF-8 output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Paths
BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_FILE = os.path.join(BENCHMARK_DIR, "temp_benchmark_transcript.jsonl")
BUN_PARSER = r"D:\AI\Projects\Personal_AI_Infrastructure\Releases\v5.0.0\.claude\PAI\TOOLS\TranscriptParser.ts"
PYTHON_ADAPTER_DIR = os.path.dirname(BENCHMARK_DIR)

# Append parent dir for importing normalizer
sys.path.append(PYTHON_ADAPTER_DIR)
from normalizers.adapters import AntigravityNormalizer

def generate_mixed_transcript(count=50000):
    print(f"[*] Generating {count} lines of mixed JSONL transcript data...")
    with open(TEST_FILE, "w", encoding="utf-8") as f:
        for i in range(count):
            # Alternate between Python-format, Bun-format, and Noise lines
            mod = i % 4
            if mod == 0:
                # Python Format user
                entry = {
                    "type": "USER_INPUT",
                    "content": f"<USER_REQUEST>Python user message {i} with some standard developer text content</USER_REQUEST>",
                    "created_at": datetime.now().isoformat()
                }
            elif mod == 1:
                # Python Format assistant
                entry = {
                    "type": "MODEL_RESPONSE",
                    "content": f"Python assistant response text {i} explaining some code mechanics.",
                    "created_at": datetime.now().isoformat()
                }
            elif mod == 2:
                # Bun format assistant
                entry = {
                    "type": "assistant",
                    "message": {
                        "content": f"Bun assistant response text {i} with typescript content blocks."
                    },
                    "created_at": datetime.now().isoformat()
                }
            else:
                # Random background noise line
                entry = {
                    "type": "system_stub",
                    "status": "idle",
                    "timestamp": datetime.now().isoformat()
                }
            f.write(json.dumps(entry) + "\n")

def benchmark_bun():
    print("[*] Benchmarking Bun parser...")
    start = time.time()
    # Execute Bun script
    env = os.environ.copy()
    if "HOME" not in env:
        env["HOME"] = env.get("USERPROFILE", "")
    res = subprocess.run(
        ["bun", "run", BUN_PARSER, TEST_FILE, "--plain"],
        capture_output=True,
        text=True,
        check=True,
        env=env
    )
    duration = time.time() - start
    # Print a small slice of output to ensure it parsed correctly
    output_preview = res.stdout.strip()[:60] + "..." if res.stdout else "Empty"
    return duration, output_preview

def benchmark_python():
    print("[*] Benchmarking Python parser...")
    normalizer = AntigravityNormalizer()
    start = time.time()
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    parsed = normalizer.parse(content)
    duration = time.time() - start
    output_preview = f"Parsed {len(parsed)} turns. Sample: {parsed[-1]['text'][:50]}..." if parsed else "Empty"
    return duration, output_preview

def main():
    generate_mixed_transcript(50000)
    
    # Run warmups
    print("[*] Running warmups...")
    try:
        benchmark_bun()
        benchmark_python()
    except Exception as e:
        print(f"[-] Warmup failed: {e}")
        return

    # Run Benchmark Rounds
    rounds = 5
    bun_times = []
    py_times = []
    
    print(f"\n[*] Executing {rounds} benchmark rounds...")
    for r in range(rounds):
        print(f"  Round {r+1}/{rounds}...")
        b_time, b_prev = benchmark_bun()
        p_time, p_prev = benchmark_python()
        bun_times.append(b_time)
        py_times.append(p_time)
        
    avg_bun = sum(bun_times) / rounds
    avg_py = sum(py_times) / rounds
    
    # Clean up test file
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)
        
    report = f"""# Head-to-Head Benchmark Report: Bun (PAI) vs. Python (ULM)
*Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*

This report compares the performance of the Bun-based `TranscriptParser.ts` from Personal AI Infrastructure against Python's `AntigravityNormalizer` from Antigravity Overdrive Sync over a 50,000-line mixed transcript JSONL payload.

## 📊 Performance Results

| Parser Engine | Average Processing Time | Delta vs. Bun | Ingestion Speed (lines/sec) |
| :--- | :---: | :---: | :---: |
| **Bun (TypeScript)** | **{avg_bun:.4f}s** | Baseline | {50000 / avg_bun:,.0f} l/s |
| **Python (3.11/3.12)** | **{avg_py:.4f}s** | {((avg_py - avg_bun)/avg_bun)*100:+.2f}% | {50000 / avg_py:,.0f} l/s |

## 🔍 Implementation & Behavior differences
- **Bun (`TranscriptParser.ts`)**: Invokes full JS runtime parsing, processes current turns selectively, extracts TTS chunks, and filters out non-assistant items. Runs as an external subprocess in this benchmark.
- **Python (`AntigravityNormalizer`)**: Runs natively inside the Python process context, parsing line-by-line using standard library `json.loads` block iterations. 
"""

    print("\n" + "="*50)
    print(report)
    print("="*50)

    # Save report to D:\AI\Antigravity outputs
    out_report = r"D:\AI\Antigravity outputs\head_to_head_report.md"
    with open(out_report, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[+] Benchmark report written to {out_report}")

if __name__ == "__main__":
    main()
