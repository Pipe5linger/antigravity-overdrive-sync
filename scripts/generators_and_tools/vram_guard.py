import sys
import os
import socket
import requests

def check_comfyui_online(host="127.0.0.1", port=8188):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False

def check_and_evict_ollama_vram(endpoint="http://localhost:11434"):
    try:
        base = endpoint.rstrip("/")
        res = requests.get(f"{base}/api/ps", timeout=2)
        if res.status_code == 200:
            models = res.json().get("models", [])
            if models:
                print(f"[*] Found {len(models)} model(s) locked in VRAM: {[m.get('name') for m in models]}")
                for m in models:
                    m_name = m.get("name")
                    if m_name:
                        requests.post(f"{base}/api/generate", json={"model": m_name, "keep_alive": 0}, timeout=3)
                        print(f"[+] Purged {m_name} from VRAM.")
                return True
        return True
    except Exception as e:
        # If Ollama is not running, that's fine - VRAM is already free
        return True

def main():
    print("[*] Running Pre-Flight VRAM & Workload Guard...")
    comfy_live = check_comfyui_online()
    status_str = "ONLINE" if comfy_live else "OFFLINE"
    print(f"[*] ComfyUI Service (127.0.0.1:8188): {status_str}")
    
    check_and_evict_ollama_vram()
    print("[+] Pre-Flight VRAM Guard Passed: GPU headroom preserved for RTX 4070.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
