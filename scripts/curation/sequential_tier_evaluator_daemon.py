"""
Sequential Multi-Tier Evaluator Daemon (Antigravity-Overdrive-Sync)
==================================================================
Monitors active tier evaluation runs and automatically chains the next tiers:
Tier 2 (Boudoir) -> Tier 3 (Couture) -> Tier 4 (Spatial)

Features:
- Seamlessly attaches to existing active evaluation runs (e.g. current T2 process).
- Automatically executes PyTorch VRAM garbage collection (/free) between tiers.
- Enforces Golden Convergence Protocol on all chained tiers.
- Emits real-time progress logging to terminal and sequential_runner.log.
"""

import sys
import os
import time
import subprocess
import argparse
import urllib.request
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

EVALUATOR_SCRIPT = Path(__file__).resolve().parent / "tier_stack_evaluator.py"
COMFY_URL = "http://127.0.0.1:8188"
LOG_DIR = Path(r"D:\AI\Projects\ComfyUI\output\tier_eval")
LOG_DIR.mkdir(parents=True, exist_ok=True)
RUNNER_LOG = LOG_DIR / "sequential_runner.log"


def log(msg: str):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line)
    try:
        with open(RUNNER_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def free_comfy_vram():
    try:
        req = urllib.request.Request(
            f"{COMFY_URL}/free",
            data=json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            log("  [Hardware] Flushed ComfyUI PyTorch VRAM cache.")
    except Exception as e:
        log(f"  [Hardware] Note: /free call returned: {e}")


def is_tier_running(tier: str) -> bool:
    try:
        import psutil
        for p in psutil.process_iter(['name', 'cmdline']):
            cmd = " ".join(p.info['cmdline'] or [])
            if "tier_stack_evaluator.py" in cmd and f"--tier {tier}" in cmd:
                return True
    except Exception:
        pass
    return False


def wait_for_tier(tier: str, poll_interval: int = 10):
    log(f"⏳ Waiting for active {tier} evaluation process to complete...")
    while is_tier_running(tier):
        time.sleep(poll_interval)
    log(f"✅ Active {tier} evaluation has completed!")


def run_tier(phase: str, tier: str, evals: int, golden_quota: int, patience: int, promote: bool = True, mode: str = "tune"):
    log("=" * 80)
    log(f"🚀 LAUNCHING EVALUATION PIPELINE: {phase} / {tier}")
    log(f"   Quota: {golden_quota} Golden Stacks | Patience: {patience} | Max Evals: {evals} | Auto-Promote: {promote}")
    log("=" * 80)

    free_comfy_vram()
    time.sleep(2)

    cmd = [
        sys.executable,
        str(EVALUATOR_SCRIPT),
        "--phase", phase,
        "--tier", tier,
        "--evals", str(evals),
        "--golden-target", "-1.0",
        "--golden-quota", str(golden_quota),
        "--patience", str(patience),
        "--mode", mode
    ]
    if promote:
        cmd.append("--promote")

    log(f"Executing: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1
    )

    for line in proc.stdout:
        clean_line = line.rstrip()
        if clean_line:
            log(f"[{tier}] {clean_line}")

    proc.wait()
    return_code = proc.returncode

    if return_code == 0:
        log(f"🏆 {tier} evaluation successfully finished with return code 0!")
    else:
        log(f"⚠️ {tier} evaluation finished with non-zero return code: {return_code}")

    free_comfy_vram()
    time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description="Sequential Multi-Tier Evaluator Daemon")
    parser.add_argument("--phase", default="Phase 3", choices=["Phase 1", "Phase 2", "Phase 3"])
    parser.add_argument("--tiers", default="T1,T2,T3,T4,T5", help="Comma-separated tiers to run in sequence")
    parser.add_argument("--mode", default="tune", choices=["tune", "search"])
    parser.add_argument("--evals", type=int, default=100)
    parser.add_argument("--golden-quota", type=int, default=5)
    parser.add_argument("--patience", type=int, default=25)
    parser.add_argument("--promote", action="store_true", default=True)
    parser.add_argument("--continuous", action="store_true", help="Repeat the cycle indefinitely without stopping")
    args = parser.parse_args()

    tier_list = [t.strip().upper() for t in args.tiers.split(",") if t.strip()]

    log("=" * 80)
    log(f"👑 VESPERA SEQUENTIAL TIER EVALUATOR DAEMON STARTED")
    log(f"   Phase Target : {args.phase}")
    log(f"   Queue Order  : {' -> '.join(tier_list)}")
    log(f"   Continuous   : {args.continuous}")
    log(f"   Log File     : {RUNNER_LOG}")
    log("=" * 80)

    cycle = 0
    while True:
        cycle += 1
        log("=" * 80)
        log(f"🔄 EXPLORATION CYCLE #{cycle} INITIATED")
        log(f"   Queue Order  : {' -> '.join(tier_list)} ({args.evals} stacks per tier)")
        log("=" * 80)

        for i, tier in enumerate(tier_list):
            if is_tier_running(tier):
                log(f"Detected currently active {tier} run. Attaching and waiting for completion...")
                wait_for_tier(tier)
                continue

            log(f"\n[Cycle #{cycle} | Step {i+1}/{len(tier_list)}] Starting {tier} evaluation ({args.evals} stacks)...")
            run_tier(
                phase=args.phase,
                tier=tier,
                evals=args.evals,
                golden_quota=args.golden_quota,
                patience=args.patience,
                promote=args.promote,
                mode=args.mode
            )
            free_comfy_vram()
            time.sleep(3)

        if not args.continuous:
            break

        log(f"\n✅ Completed Cycle #{cycle}! Purging VRAM cache and cycling immediately to next pass...")
        free_comfy_vram()
        time.sleep(5)

    log("\n" + "=" * 80)
    log("🎉 ALL QUEUED TIERS HAVE COMPLETED SUCCESSFULLY!")
    log(f"   Check your updated recipes in data/tier_lora_recipes_{args.phase.replace(' ', '').lower()}.json")
    log("=" * 80)


if __name__ == "__main__":
    main()

