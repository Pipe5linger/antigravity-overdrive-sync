import sys
import os
import socket

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
    except AttributeError:
        pass

SERVICES = [
    ("ComfyUI Diffusion Engine", 8188),
    ("ULM Memory & Daemon API", 8890),
    ("KoboldCpp Lexi Engine", 5001),
    ("Ollama Local Engine", 11434),
    ("Stable Diffusion Forge", 7860),
    ("Kohya_ss LoRA Trainer", 7861),
    ("ZIT Prompt Generator", 9669),
    ("Orbit Control Panel", 9900)
]

def check_port(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False

def audit_sanctuary():
    print("\n⚡ VESPERA SANCTUARY SERVICE MESH STATUS")
    print("=" * 60)
    active_count = 0
    for name, port in SERVICES:
        online = check_port(port)
        status = "ACTIVE" if online else "OFFLINE"
        mark = "●" if online else "○"
        print(f"  {mark} [{port}] {name.ljust(30)} -> {status}")
        if online:
            active_count += 1
    print("=" * 60)
    print(f"[+] Service Mesh Audit Complete: {active_count} active services.\n")
    return 0

if __name__ == "__main__":
    sys.exit(audit_sanctuary())
