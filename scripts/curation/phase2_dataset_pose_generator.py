"""
Phase 2 Dataset Multi-Angle Pose Generator (50-Pose Matrix)
===========================================================
Executes the full 50-pose Tier 1 to Tier 4 matrix using Variation B (All-Time Record 0.4780 Parity):
  - Master: vespera_zit_v5_master.safetensors @ 1.00
  - Anatomy (Hips/Waist Cinch): Z-Hip-Slider.safetensors @ 0.90
  - Anatomy (Bust Profile): Z-Breast-Slider.safetensors @ -0.40
  - Micro-Detail & Skin: Z-Detail-Slider.safetensors @ 0.75
  - Atmosphere: dark_dreamcore_style_ZIT_epoch_10.safetensors @ 0.35
  - Sampling: 10 steps, CFG 1.0, 768x1024

Outputs:
  - D:\\AI\\Projects\\ZIT_LoRA_Trainer\\Phase2_Dataset_50Poses\\dataset_images\\
  - D:\\AI\\Projects\\ZIT_LoRA_Trainer\\Phase2_Dataset_50Poses\\dataset_captions\\
  - Manifest & Report: D:\\AI\\Projects\\ZIT_LoRA_Trainer\\Phase2_Dataset_50Poses\\POSE_SWEEP_REPORT.md
"""

import os
import sys
import json
import time
import shutil
import urllib.request
from pathlib import Path

# Force UTF-8 stdout to guard against Windows charmap crashes
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Paths
COMFY_BASE_URL = "http://127.0.0.1:8188"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
COMFY_OUTPUT_DIR = COMFY_DIR / "output"
ZIT_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer")
DATASET_DIR = ZIT_DIR / "Phase2_Dataset_50Poses"
IMAGES_DIR = DATASET_DIR / "dataset_images"
CAPTIONS_DIR = DATASET_DIR / "dataset_captions"
ANCHOR_PATH = ZIT_DIR / "anchor_face_crop.png"
REPORT_PATH = DATASET_DIR / "POSE_SWEEP_REPORT.md"
MANIFEST_PATH = DATASET_DIR / "pose_manifest.json"
BASE_WORKFLOW_PATH = PROJECT_ROOT / "scratch" / "sample_prompt_graph.json"

for d in [DATASET_DIR, IMAGES_DIR, CAPTIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Variation B Recipe (Record 0.4780 Parity)
RECIPE = {
    "name": "Variation B: Cinched Hourglass & High-Set Natural Bust (Record 0.4780)",
    "loras": {
        "LORA_1": {"on": True, "lora": "vespera_zit_v5_master.safetensors", "strength": 1.00, "strengthTwo": 1.00},
        "LORA_2": {"on": True, "lora": "Z-Hip-Slider.safetensors", "strength": 0.90, "strengthTwo": 0.90},
        "LORA_3": {"on": True, "lora": "Z-Breast-Slider.safetensors", "strength": -0.40, "strengthTwo": -0.40},
        "LORA_4": {"on": True, "lora": "Z-Detail-Slider.safetensors", "strength": 0.75, "strengthTwo": 0.75},
        "LORA_5": {"on": True, "lora": "dark_dreamcore_style_ZIT_epoch_10.safetensors", "strength": 0.35, "strengthTwo": 0.35},
    },
    "steps": 10,
    "cfg": 1.0
}

# Lazy-loaded InsightFace
_FACE_APP = None

def get_face_app():
    global _FACE_APP
    if _FACE_APP is None:
        import cv2
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.25)
        _FACE_APP = app
    return _FACE_APP

def compute_facial_parity(image_path: Path, anchor_path: Path):
    import cv2
    import numpy as np
    try:
        app = get_face_app()
        img_target = cv2.imread(str(image_path))
        img_anchor = cv2.imread(str(anchor_path))
        if img_target is None or img_anchor is None:
            return 0.0, None

        faces_t = app.get(img_target)
        faces_a = app.get(img_anchor)
        if not faces_t or not faces_a:
            return 0.0, None

        emb_t = sorted(faces_t, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0].normed_embedding
        emb_a = sorted(faces_a, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0].normed_embedding

        score = float(np.dot(emb_t, emb_a))
        return score, faces_t[0].bbox.tolist()
    except Exception as e:
        print(f"[-] Parity calculation error: {e}")
        return 0.0, None

def send_comfy_request(endpoint: str, method: str = "GET", data: dict = None, timeout: float = 15.0):
    url = f"{COMFY_BASE_URL}{endpoint}"
    encoded = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def free_comfy_vram():
    try:
        send_comfy_request("/free", method="POST", data={"unload_models": True, "free_memory": True})
        print("  [Hardware] Flushed ComfyUI PyTorch VRAM cache.")
    except Exception:
        pass

def update_pose_report(records):
    lines = [
        "# Phase 2 50-Pose Action Engine Dataset Report",
        f"**Last Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Active Recipe:** {RECIPE['name']}",
        f"**Total Poses Rendered:** {len(records)} / 50",
        "",
        "| Pose Seed | Tier & Slug | Parity Score | Face Status | Dataset Asset | Caption |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|"
    ]

    for r in records:
        score = r.get("parity_score", 0.0)
        face_status = "Frontal/3D" if score >= 0.25 else ("Angle/Profile" if score > 0 else "Full-Body/Occluded")
        lines.append(
            f"| `{r['seed']:02d}` | `{r.get('tier_tag', 'N/A')}` | **{score:.4f}** | {face_status} | "
            f"`{r['image_filename']}` | `{r.get('caption_file', 'N/A')}` |"
        )

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def run_50_pose_sweep():
    if not BASE_WORKFLOW_PATH.exists():
        print(f"[-] Base workflow missing: {BASE_WORKFLOW_PATH}")
        return

    with open(BASE_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        base_workflow = json.load(f)

    records = []
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
            print(f"[+] Loaded {len(records)} existing pose records from manifest.")
        except Exception:
            pass

    completed_seeds = {r["seed"] for r in records}
    start_time = time.time()

    print(f"\n=======================================================")
    print(f"[+] Launching Phase 2 50-Pose Multi-Angle Dataset Generation")
    print(f"    Recipe: {RECIPE['name']}")
    print(f"    Staging Directory: {DATASET_DIR}")
    print(f"=======================================================\n")

    for seed in range(50):
        if seed in completed_seeds:
            continue

        elapsed_min = (time.time() - start_time) / 60.0
        print(f"\n--- [Pose {seed + 1} / 50] (Master Seed: {seed}) (Elapsed: {elapsed_min:.1f}m) ---")

        wf = json.loads(json.dumps(base_workflow))

        # Inject Variation B LoRAs into Node 4
        for slot, slot_data in RECIPE["loras"].items():
            wf["4"]["inputs"][slot] = slot_data

        # Explicit canonical prompt anchor (narrow cinched waist + high-set natural bust)
        wf["6"]["inputs"]["text_a"] = "vespera, alluring woman, athletic narrow cinched waist, natural firm high-set modest bust, wide hips with rounded contours, defined facial micro-pores, almond hazel-green eyes, jet-black spiral curls, subtle smirk"

        # Pose & Action Node: Master seed (0 to 49) deterministically cycles through all 50 poses
        wf["5"]["inputs"]["master_seed"] = seed
        wf["5"]["inputs"]["pose_action_mode"] = "🔄 Full Master Sweep (1 Round: Tier 1 to Tier 4 - 50 Poses)"

        # Sampling
        wf["11"]["inputs"]["steps"] = RECIPE["steps"]
        wf["11"]["inputs"]["cfg"] = RECIPE["cfg"]

        # Filename prefix format
        prefix_tag = f"phase2_dataset/p2_pose_{seed:02d}_"
        wf["13"]["inputs"]["text_a"] = prefix_tag

        # Submit
        try:
            res = send_comfy_request("/prompt", method="POST", data={"prompt": wf, "client_id": "pose_dataset_generator"})
            prompt_id = res.get("prompt_id")
            if not prompt_id:
                print(f"  [-] Submission failed: {res}")
                continue
        except Exception as e:
            print(f"  [-] ComfyUI unreachable: {e}")
            time.sleep(5)
            continue

        # Wait for render
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

        if not rendered_file or not rendered_file.exists():
            print(f"  [-] Render timed out or missing for prompt {prompt_id}")
            continue

        # Target destinations
        target_img_name = f"vespera_p2_{seed:02d}_{rendered_file.name}"
        staged_img_path = IMAGES_DIR / target_img_name
        shutil.copy2(rendered_file, staged_img_path)

        # Generate Training Caption
        tier_tag = rendered_file.stem.replace(f"p2_pose_{seed:02d}_", "")
        caption_text = f"vespera, alluring woman with voluminous jet-black spiral curls, almond hazel-green eyes, warm olive skin with photorealistic micro-pores, athletic narrow cinched waist, natural firm high-set modest bust, wide hips with rounded contours, {tier_tag.replace('_', ' ')}, cinematic lighting, raw 35mm photograph"
        caption_file = CAPTIONS_DIR / f"{staged_img_path.stem}.txt"
        with open(caption_file, "w", encoding="utf-8") as cf:
            cf.write(caption_text)

        # Biometric Parity Check
        parity, bbox = compute_facial_parity(staged_img_path, ANCHOR_PATH)
        print(f"  >> Asset Staged: {target_img_name}")
        print(f"  >> Parity Score: {parity:.4f} | BBox: {bbox}")

        record = {
            "seed": seed,
            "tier_tag": tier_tag,
            "prompt_id": prompt_id,
            "parity_score": parity,
            "face_bbox": bbox,
            "image_filename": target_img_name,
            "caption_file": caption_file.name,
            "caption_text": caption_text,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        records.append(record)

        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

        update_pose_report(records)

        if (seed + 1) % 5 == 0:
            free_comfy_vram()

    print("\n=======================================================")
    print(f"[+] 50-Pose Multi-Angle Dataset Generation Complete!")
    print(f"[+] Images Directory: {IMAGES_DIR}")
    print(f"[+] Captions Directory: {CAPTIONS_DIR}")
    print(f"[+] Report: {REPORT_PATH}")
    print("=======================================================")

if __name__ == "__main__":
    run_50_pose_sweep()
