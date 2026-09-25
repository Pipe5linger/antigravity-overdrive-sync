#!/usr/bin/env python3
"""
Playbook: port_audit.py
Inspects the connectivity and availability of local Sanctuary service ports:
- 8188: ComfyUI Engine
- 7860: Stable Diffusion Forge
- 11434: Ollama Local Inference
- 5001: KoboldCpp Uncensored Server
- 8890: ULM Webhook & API
- 9900: Antigravity Orbit Control Panel

Usage:
    python scripts/playbooks/port_audit.py [--json]
"""

import sys
import socket
import json
import argparse

# Enforce UTF-8 on Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

SERVICES = {
    8188: "ComfyUI Workflow Engine",
    7860: "SD Forge WebUI",
    11434: "Ollama Local Engine",
    5001: "KoboldCpp Uncensored Server",
    8890: "ULM Memory Daemon / API",
    9900: "Antigravity Orbit Control Panel"
}

def check_ports(output_json=False):
    status = {}
    for port, name in SERVICES.items():
        is_open = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    is_open = True
        except Exception:
            pass
        status[port] = {"name": name, "online": is_open}

    if output_json:
        print(json.dumps(status, indent=2))
        return

    print("=== 🌐 Workstation Service Port Audit ===")
    for port, info in status.items():
        state = "🟢 ONLINE" if info["online"] else "⚪ OFFLINE"
        print(f"  • Port {port:<6} [{info['name']:<30}] : {state}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit workstation AI service ports")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    check_ports(output_json=args.json)
