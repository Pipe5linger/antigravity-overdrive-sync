"""
Body Proportion Calibration Test
================================
Renders Pose 15 (T2_01_Kneeling_Frontal_Proportions) across 3 targeted anatomical recipes
specifically tuning:
  1. A more cinched, narrow waistline
  2. A slightly smaller, high-set natural bust (reducing breast slider / applying physique weights)
"""

import json
import time
import sys
import urllib.request
from pathlib import Path

# Force UTF-8 stdout to prevent Windows charmap crashes
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COMFY_BASE_URL = "http://127.0.0.1:8188"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
COMFY_OUTPUT_DIR = COMFY_DIR / "output"
TEST_OUT_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\Phase2_Dataset_50Poses\calibration_waist_bust")
TEST_OUT_DIR.mkdir(parents=True, exist_ok=True)
BASE_WORKFLOW_PATH = PROJECT_ROOT / "scratch" / "sample_prompt_graph.json"

RECIPES = [
    {
        "name": "Variation_A_Physique_Plus_HipCinch",
        "desc": "Vespera Body Physique (0.85) + Z-Hip-Slider (0.80) + Z-Breast-Slider (-0.30)",
        "loras": {
            "LORA_1": {"on": True, "lora": "vespera_zit_v5_master.safetensors", "strength": 1.00, "strengthTwo": 1.00},
            "LORA_2": {"on": True, "lora": "Vespera_Body_Physique_v1_ComfyNative.safetensors", "strength": 0.85, "strengthTwo": 0.85},
            "LORA_3": {"on": True, "lora": "Z-Hip-Slider.safetensors", "strength": 0.80, "strengthTwo": 0.80},
            "LORA_4": {"on": True, "lora": "Z-Breast-Slider.safetensors", "strength": -0.30, "strengthTwo": -0.30},
            "LORA_5": {"on": True, "lora": "Z-Detail-Slider.safetensors", "strength": 0.70, "strengthTwo": 0.70},
        }
    },
    {
        "name": "Variation_B_Hourglass_Plus_NegativeBreast",
        "desc": "Z-Hip-Slider (0.90) + Z-Breast-Slider (-0.40) + Z-Detail-Slider (0.75)",
        "loras": {
            "LORA_1": {"on": True, "lora": "vespera_zit_v5_master.safetensors", "strength": 1.00, "strengthTwo": 1.00},
            "LORA_2": {"on": True, "lora": "Z-Hip-Slider.safetensors", "strength": 0.90, "strengthTwo": 0.90},
            "LORA_3": {"on": True, "lora": "Z-Breast-Slider.safetensors", "strength": -0.40, "strengthTwo": -0.40},
            "LORA_4": {"on": True, "lora": "Z-Detail-Slider.safetensors", "strength": 0.75, "strengthTwo": 0.75},
            "LORA_5": {"on": True, "lora": "dark_dreamcore_style_ZIT_epoch_10.safetensors", "strength": 0.35, "strengthTwo": 0.35},
        }
    },
    {
        "name": "Variation_C_Pure_Vespera_Physique_Balanced",
        "desc": "Vespera Body Physique (1.00) + Z-Hip-Slider (0.65) + Zero Breast Boost",
        "loras": {
            "LORA_1": {"on": True, "lora": "vespera_zit_v5_master.safetensors", "strength": 1.00, "strengthTwo": 1.00},
            "LORA_2": {"on": True, "lora": "Vespera_Body_Physique_v1_ComfyNative.safetensors", "strength": 1.00, "strengthTwo": 1.00},
            "LORA_3": {"on": True, "lora": "Z-Hip-Slider.safetensors", "strength": 0.65, "strengthTwo": 0.65},
            "LORA_4": {"on": True, "lora": "Z-Detail-Slider.safetensors", "strength": 0.80, "strengthTwo": 0.80},
            "LORA_5": {"on": True, "lora": "dark_dreamcore_style_ZIT_epoch_10.safetensors", "strength": 0.40, "strengthTwo": 0.40},
        }
    }
]

def send_comfy_request(endpoint: str, method: str = "GET", data: dict = None):
    url = f"{COMFY_BASE_URL}{endpoint}"
    encoded = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run():
    with open(BASE_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        base_wf = json.load(f)

    for idx, var in enumerate(RECIPES):
        print(f"\n[+] Rendering {var['name']} ({var['desc']})...")
        wf = json.loads(json.dumps(base_wf))

        # LoRAs
        for slot, slot_data in var["loras"].items():
            wf["4"]["inputs"][slot] = slot_data

        # Prompt anchor with cinched waist and natural high-set bust
        wf["6"]["inputs"]["text_a"] = "vespera, alluring woman, athletic narrow cinched waist, defined vertical navel, natural firm high-set modest bust, wide hips with rounded contours, defined facial micro-pores, almond hazel-green eyes, jet-black spiral curls, subtle smirk"

        # Pose 15: T2_01_Kneeling_Frontal_Proportions (direct anatomy proportion test)
        wf["5"]["inputs"]["master_seed"] = 15
        wf["5"]["inputs"]["pose_action_mode"] = "🔄 Full Master Sweep (1 Round: Tier 1 to Tier 4 - 50 Poses)"

        wf["11"]["inputs"]["steps"] = 10
        wf["11"]["inputs"]["cfg"] = 1.0

        prefix = f"calibration_waist_bust/{var['name']}_"
        wf["13"]["inputs"]["text_a"] = prefix

        res = send_comfy_request("/prompt", method="POST", data={"prompt": wf, "client_id": "calibration_test"})
        prompt_id = res["prompt_id"]

        rendered_file = None
        wait_start = time.time()
        while time.time() - wait_start < 90:
            try:
                hist = send_comfy_request(f"/history/{prompt_id}")
                if prompt_id in hist:
                    outputs = hist[prompt_id].get("outputs", {})
                    for nid, nout in outputs.items():
                        if "images" in nout and len(nout["images"]) > 0:
                            img_info = nout["images"][0]
                            subf = img_info.get("subfolder", "")
                            fname = img_info.get("filename", "")
                            rendered_file = COMFY_OUTPUT_DIR / subf / fname
                            break
                    if rendered_file:
                        break
            except Exception:
                pass
            time.sleep(1.0)

        if rendered_file and rendered_file.exists():
            import shutil
            dest = TEST_OUT_DIR / rendered_file.name
            shutil.copy2(rendered_file, dest)
            print(f"  [+] Rendered & Saved: {dest}")

if __name__ == "__main__":
    run()
