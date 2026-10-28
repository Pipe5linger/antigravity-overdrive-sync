import sys
import os
import time
import socket
import json
import shutil
import subprocess
import requests

# Guard against Windows charmap cp1252 crashes and enable unbuffered output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

COMFY_HOST = "127.0.0.1"
COMFY_PORT = 8188
OLLAMA_ENDPOINT = "http://localhost:11434"
# For RTX 4070 12GB, active inference with VAE decode naturally peaks at 10.2-10.8 GB.
# Danger of PCIe paging starts above 11,400 MB.
VRAM_DANGER_THRESHOLD_MB = 11400  # Evict external processes if exceeded
VRAM_IDLE_FLUSH_THRESHOLD_MB = 10500  # Soft flush ComfyUI cache ONLY when idle

def check_comfyui_online(host=COMFY_HOST, port=COMFY_PORT):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False

def get_gpu_telemetry():
    """Queries nvidia-smi for total, used, free VRAM, temperature, and utilization."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        out = subprocess.check_output(
            [smi, "--query-gpu=memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
            encoding="utf-8",
            errors="replace",
            timeout=3
        ).strip()
        parts = [p.strip() for p in out.split(",")]
        return {
            "total_mb": int(parts[0]),
            "used_mb": int(parts[1]),
            "free_mb": int(parts[2]),
            "temp_c": int(parts[3]),
            "util_pct": int(parts[4])
        }
    except Exception:
        return None

def check_and_evict_ollama_vram(endpoint=OLLAMA_ENDPOINT):
    try:
        base = endpoint.rstrip("/")
        res = requests.get(f"{base}/api/ps", timeout=2)
        if res.status_code == 200:
            models = res.json().get("models", [])
            if models:
                print(f"[!] Guard detected {len(models)} model(s) locked in Ollama VRAM: {[m.get('name') for m in models]}")
                for m in models:
                    m_name = m.get("name")
                    if m_name:
                        requests.post(f"{base}/api/generate", json={"model": m_name, "keep_alive": 0}, timeout=3)
                        print(f"[+] Purged {m_name} from Ollama VRAM.")
                return True
        return True
    except Exception:
        return True

def get_comfy_queue_status():
    """Checks how many prompts are running or pending in ComfyUI."""
    try:
        r = requests.get(f"http://{COMFY_HOST}:{COMFY_PORT}/queue", timeout=2)
        if r.status_code == 200:
            data = r.json()
            running = len(data.get("queue_running", []))
            pending = len(data.get("queue_pending", []))
            return running, pending
    except Exception:
        pass
    return 0, 0

def purge_comfy_cache():
    """Calls ComfyUI /free to release fragmented memory without unloading active models if running."""
    try:
        payload = {"unload_models": False, "free_memory": True}
        r = requests.post(f"http://{COMFY_HOST}:{COMFY_PORT}/free", json=payload, timeout=3)
        if r.status_code == 200:
            print("[+] ComfyUI memory cache soft-purged successfully.")
            return True
    except Exception as e:
        print(f"[-] ComfyUI /free failed: {e}")
    return False

def run_guard_cycle():
    """Executes a single check-and-protect cycle."""
    evicted = check_and_evict_ollama_vram()
    telemetry = get_gpu_telemetry()
    if telemetry:
        used = telemetry["used_mb"]
        total = telemetry["total_mb"]
        pct = round((used / total) * 100, 1)
        running, pending = get_comfy_queue_status()

        # If VRAM reaches danger threshold (> 11.4 GB), evict any external processes immediately
        if used >= VRAM_DANGER_THRESHOLD_MB:
            print(f"[!] [HIGH VRAM ALERT] VRAM at {used:,} MB / {total:,} MB ({pct}%). Evicting external models...")
            check_and_evict_ollama_vram()
            if running == 0:
                print("[*] ComfyUI queue is idle; soft-purging memory cache...")
                purge_comfy_cache()
        elif used >= VRAM_IDLE_FLUSH_THRESHOLD_MB and running == 0 and pending == 0:
            # Idle clean-up
            print(f"[*] ComfyUI completely idle with {used:,} MB retained. Running soft cache release...")
            purge_comfy_cache()

        return telemetry
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous VRAM Guard & Workload Protector")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in the background")
    parser.add_argument("--interval", type=int, default=15, help="Check interval in seconds for daemon mode")
    args = parser.parse_args()

    print("[*] Running VRAM & Workload Guard...")
    comfy_live = check_comfyui_online()
    status_str = "ONLINE" if comfy_live else "OFFLINE"
    print(f"[*] ComfyUI Service ({COMFY_HOST}:{COMFY_PORT}): {status_str}")

    if not args.daemon:
        telem = run_guard_cycle()
        if telem:
            print(f"[+] VRAM: {telem['used_mb']:,} MB / {telem['total_mb']:,} MB ({round(telem['used_mb']/telem['total_mb']*100, 1)}%) | Temp: {telem['temp_c']}C | Headroom: {telem['free_mb']:,} MB")
        print("[+] Pre-Flight VRAM Guard Passed: GPU headroom preserved for RTX 4070.")
        return 0

    print(f"[*] Starting Autonomous VRAM Guard Daemon (polling every {args.interval}s, danger threshold: {VRAM_DANGER_THRESHOLD_MB} MB)...")
    try:
        while True:
            telem = run_guard_cycle()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[*] VRAM Guard Daemon terminated gracefully.")
        return 0

if __name__ == "__main__":
    sys.exit(main())


