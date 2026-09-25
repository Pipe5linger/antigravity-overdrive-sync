#!/usr/bin/env python3
"""
Playbook: comfy_queue.py
Inspects the active ComfyUI generation queue, currently executing prompt ID,
and pending task queue on http://127.0.0.1:8188.

Usage:
    python scripts/playbooks/comfy_queue.py [--json]
"""

import sys
import json
import argparse
import urllib.request
import urllib.error

# Enforce UTF-8 on Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

def check_queue(output_json=False):
    url = "http://127.0.0.1:8188/queue"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Antigravity-ULM"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if output_json:
            print(json.dumps(data, indent=2))
            return

        running = data.get("queue_running", [])
        pending = data.get("queue_pending", [])

        print("=== 🎨 ComfyUI Generation Pipeline (Port 8188) ===")
        print(f"  • Active Prompts Running : {len(running)}")
        print(f"  • Tasks Queued / Pending : {len(pending)}")

        if running:
            print("\n--- Running Tasks ---")
            for item in running:
                pid = item[1] if len(item) > 1 else "Unknown"
                print(f"  • Prompt ID: {pid}")

        if pending:
            print("\n--- Pending Tasks ---")
            for item in pending:
                pid = item[1] if len(item) > 1 else "Unknown"
                print(f"  • Prompt ID: {pid}")

        if not running and not pending:
            print("  • Status: IDLE (Queue is empty)")

    except urllib.error.URLError:
        print("⚪ ComfyUI is OFFLINE or unreachable on http://127.0.0.1:8188.")
    except Exception as e:
        print(f"[-] Error querying ComfyUI queue: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query ComfyUI active generation queue")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    check_queue(output_json=args.json)
