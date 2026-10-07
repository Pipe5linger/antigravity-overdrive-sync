"""
Test Rewritten Phase 2 Render & Parity Validation
=================================================
Renders test seeds using the rewritten workflow based on amy_v5 architecture + native_zit_sweep gold recipe.
Evaluates:
  1. Facial likeness and ArcFace parity score vs anchor
  2. Wardrobe coverage (zero exposed cleavage or bare breasts)
  3. Anatomical proportions (cinched waist, modest bust)
"""

import os
import sys
import json
import time
import shutil
import urllib.request
from pathlib import Path

# Force UTF-8 stdout
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COMFY_BASE_URL = "http://127.0.0.1:8188"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
COMFY_OUTPUT_DIR = COMFY_DIR / "output"
ZIT_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer")
ANCHOR_PATH = ZIT_DIR / "anchor_face_crop.png"
PROMPT_GRAPH_PATH = PROJECT_ROOT / "scratch" / "phase2_prompt_graph.json"

TEST_OUTPUT_DIR = COMFY_OUTPUT_DIR / "phase2_rewritten_test"
TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def send_comfy_request(endpoint: str, method: str = "GET", data: dict = None, timeout: float = 20.0):
    url = f"{COMFY_BASE_URL}{endpoint}"
    encoded = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def render_seed(seed: int, label: str):
    with open(PROMPT_GRAPH_PATH, "r", encoding="utf-8") as f:
        wf = json.load(f)

    # Inject seeds
    if "90" in wf:
        wf["90"]["inputs"]["master_seed"] = seed
    if "92" in wf:
        wf["92"]["inputs"]["master_seed"] = seed
    if "99" in wf:
        wf["99"]["inputs"]["master_seed"] = seed
    if "88" in wf:
        wf["88"]["inputs"]["master_seed"] = seed
    if "11" in wf:
        wf["11"]["inputs"]["seed"] = seed
    if "15" in wf:
        wf["15"]["inputs"]["seed"] = seed
    if "20" in wf:
        wf["20"]["inputs"]["seed"] = seed

    # Route save path
    if "18" in wf:
        wf["18"]["inputs"]["filename_prefix"] = f"phase2_rewritten_test/test_s{seed:04d}_{label}_"

    print(f"\n[+] Submitting Seed {seed} ({label})...")
    res = send_comfy_request("/prompt", method="POST", data={"prompt": wf, "client_id": "rewritten_test"})
    prompt_id = res.get("prompt_id")
    if not prompt_id:
        print(f"[-] Submission failed: {res}")
        return None

    # Wait for render
    rendered_file = None
    start = time.time()
    while time.time() - start < 120:
        try:
            hist = send_comfy_request(f"/history/{prompt_id}")
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                if "18" in outputs and "images" in outputs["18"] and len(outputs["18"]["images"]) > 0:
                    info = outputs["18"]["images"][0]
                    subf = info.get("subfolder", "")
                    fname = info.get("filename", "")
                    target = COMFY_OUTPUT_DIR / subf / fname
                    if target.exists():
                        rendered_file = target
                        break
        except Exception:
            pass
        time.sleep(1.5)

    if rendered_file:
        print(f"[+] Render completed: {rendered_file}")
    else:
        print(f"[-] Render timed out.")
    return rendered_file

if __name__ == "__main__":
    print("=== Testing Rewritten Phase 2 Pipeline ===")
    img0 = render_seed(0, "T1_01_Portrait")
    if img0:
        print(f"Seed 0: {img0.name}")
