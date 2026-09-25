#!/usr/bin/env python3
"""
Playbook: gpu_guard.py
Monitors RTX 4070 12GB VRAM allocation, temperature, and compute load,
and optionally triggers a PyTorch CUDA cache flush.

Usage:
    python scripts/playbooks/gpu_guard.py [--purge]
"""

import sys
import shutil
import argparse
import subprocess

# Enforce UTF-8 on Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

def guard(purge=False):
    print("=== ⚡ NVIDIA RTX 4070 VRAM & Hardware Guard ===")
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            out = subprocess.check_output(
                [smi, "--query-gpu=memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
                encoding="utf-8",
                errors="replace",
                timeout=3
            ).strip()
            total, used, free, temp, util = [x.strip() for x in out.split(",")]
            pct = int(int(used) / int(total) * 100)
            print(f"  • VRAM Total       : {int(total):,} MB")
            print(f"  • VRAM In Use      : {int(used):,} MB ({pct}%)")
            print(f"  • VRAM Available   : {int(free):,} MB")
            print(f"  • Core Temperature : {temp} °C")
            print(f"  • GPU Utilization  : {util} %")
        except Exception as e:
            print(f"[-] nvidia-smi query failed: {e}")
    else:
        print("[-] nvidia-smi not detected in PATH.")

    if purge:
        print("\n[*] Initiating CUDA cache purge...")
        try:
            import gc
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                print("[+] PyTorch CUDA cache and IPC memory cleared successfully.")
            else:
                print("[-] PyTorch CUDA device not initialized in current interpreter.")
        except ImportError:
            print("[-] PyTorch not installed in this environment; ran Python gc.collect().")
        except Exception as e:
            print(f"[-] Cache purge error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect or purge GPU VRAM")
    parser.add_argument("--purge", "-p", action="store_true", help="Flush PyTorch CUDA memory cache")
    args = parser.parse_args()

    guard(purge=args.purge)
