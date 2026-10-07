"""
Tier 3 Wardrobe Clothedness & Silhouette Test
============================================
Tests Seed 26 (T3_02_Ivory_Power_Suit) to verify:
  1. No nudity or exposed cleavage leakage
  2. Cinched waistline and natural high-set bust
Testing two replacement candidates for Z-Breast-Slider:
  - Candidate 1: Vespera_Body_Physique_v1_ComfyNative (0.85) + Z-Hip-Slider (0.80)
  - Candidate 2: ZIB_SkinnyVoluptousSlider_v5.1 (0.60) + Z-Hip-Slider (0.90)
"""

import json
import time
import sys
import shutil
import urllib.request
from pathlib import Path

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COMFY_BASE_URL = "http://127.0.0.1:8188"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
COMFY_OUTPUT_DIR = COMFY_DIR / "output"
TEST_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\Phase2_Dataset_50Poses\wardrobe_bias_test")
TEST_DIR.mkdir(parents=True, exist_ok=True)
BASE_WORKFLOW_PATH = PROJECT_ROOT / "scratch" / "my_fav_prompt_graph.json"

VESPERA_CANONICAL_PROMPT = (
    "vespera, alluring woman of French-Levantine and Mediterranean heritage with athletic narrow cinched waist, "
    "wide hips with full perfectly rounded gluteal contours, toned thighs, and natural firm high-set modest bust, "
    "unblemished luminous warm olive skin retaining photorealistic micro-pores, skin texture, and golden undertones with specular highlights on cheekbones and collarbones, "
    "sculpted facial structure with high cheekbones and soft-tapered button nose, captivating deep hazel-green almond-shaped eyes with soft-smudged smoky eyeliner, "
    "full soft satin lips with subtle natural moisture and a tiny beauty mark beside upper-left lip corner, voluminous jet-black 3B/3C spiral corkscrew curls with fine interwoven electric-indigo highlights framing face, "
    "subtle asymmetrical half-smirk"
)

CANDIDATES = [
    {
        "name": "Candidate_1_VesperaPhysique",
        "desc": "Vespera_Body_Physique_v1 (0.85) + Z-Hip-Slider (0.80) [Zero Breast Slider]",
        "loras": {
            "LORA_1": {"on": True, "lora": "vespera_zit_v5_master.safetensors", "strength": 1.00, "strengthTwo": 1.00},
            "LORA_2": {"on": True, "lora": "Vespera_Body_Physique_v1_ComfyNative.safetensors", "strength": 0.85, "strengthTwo": 0.85},
            "LORA_3": {"on": True, "lora": "Z-Hip-Slider.safetensors", "strength": 0.80, "strengthTwo": 0.80},
            "LORA_4": {"on": True, "lora": "Z-Detail-Slider.safetensors", "strength": 0.75, "strengthTwo": 0.75},
            "LORA_5": {"on": True, "lora": "dark_dreamcore_style_ZIT_epoch_10.safetensors", "strength": 0.35, "strengthTwo": 0.35},
        }
    },
    {
        "name": "Candidate_2_SkinnyVoluptuous",
        "desc": "ZIB_SkinnyVoluptousSlider (0.60) + Z-Hip-Slider (0.90) [Zero Breast Slider]",
        "loras": {
            "LORA_1": {"on": True, "lora": "vespera_zit_v5_master.safetensors", "strength": 1.00, "strengthTwo": 1.00},
            "LORA_2": {"on": True, "lora": "Z-Hip-Slider.safetensors", "strength": 0.90, "strengthTwo": 0.90},
            "LORA_3": {"on": True, "lora": "ZIB_SkinnyVoluptousSlider_v5.1.safetensors", "strength": 0.60, "strengthTwo": 0.60},
            "LORA_4": {"on": True, "lora": "Z-Detail-Slider.safetensors", "strength": 0.75, "strengthTwo": 0.75},
            "LORA_5": {"on": True, "lora": "dark_dreamcore_style_ZIT_epoch_10.safetensors", "strength": 0.35, "strengthTwo": 0.35},
        }
    }
]

def send_comfy_request(endpoint: str, method: str = "GET", data: dict = None):
    url = f"{COMFY_BASE_URL}{endpoint}"
    encoded = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20.0) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run():
    with open(BASE_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        base_wf = json.load(f)

    for cand in CANDIDATES:
        print(f"\n[+] Testing {cand['name']} ({cand['desc']})...")
        wf = json.loads(json.dumps(base_wf))

        for slot, slot_data in cand["loras"].items():
            wf["3"]["inputs"][slot] = slot_data

        # Pose 26 (Seed 26 = T3_02_Ivory_Power_Suit)
        seed = 26
        if "90" in wf:
            wf["90"]["inputs"]["master_seed"] = seed
        if "92" in wf:
            wf["92"]["inputs"]["master_seed"] = seed
            wf["92"]["inputs"]["pose_action_mode"] = "🔁 Matrix Sweep (40 Rounds - 2000 Batch)"
        if "99" in wf:
            wf["99"]["inputs"]["master_seed"] = seed
        if "88" in wf:
            wf["88"]["inputs"]["master_seed"] = seed
            wf["88"]["inputs"]["subject_core"] = VESPERA_CANONICAL_PROMPT
        if "11" in wf:
            wf["11"]["inputs"]["seed"] = seed
            wf["11"]["inputs"]["steps"] = 10
            wf["11"]["inputs"]["cfg"] = 1.0
        if "15" in wf:
            wf["15"]["inputs"]["seed"] = seed
        if "20" in wf:
            wf["20"]["inputs"]["seed"] = seed

        res = send_comfy_request("/prompt", method="POST", data={"prompt": wf, "client_id": "wardrobe_bias_test"})
        prompt_id = res["prompt_id"]

        rendered_file = None
        wait_start = time.time()
        while time.time() - wait_start < 120:
            try:
                hist = send_comfy_request(f"/history/{prompt_id}")
                if prompt_id in hist:
                    outputs = hist[prompt_id].get("outputs", {})
                    for nid in ["18", "20", "15", "12"]:
                        if nid in outputs and "images" in outputs[nid] and len(outputs[nid]["images"]) > 0:
                            img_info = outputs[nid]["images"][0]
                            subf = img_info.get("subfolder", "")
                            fname = img_info.get("filename", "")
                            candidate_path = COMFY_OUTPUT_DIR / subf / fname
                            if candidate_path.exists():
                                rendered_file = candidate_path
                                break
                    if rendered_file:
                        break
            except Exception:
                pass
            time.sleep(1.5)

        if rendered_file and rendered_file.exists():
            dest = TEST_DIR / f"{cand['name']}_{rendered_file.name}"
            shutil.copy2(rendered_file, dest)
            print(f"  [+] Saved test render: {dest}")

if __name__ == "__main__":
    run()
