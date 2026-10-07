"""
Phase 2 100% Native ZIT Architecture Optimizer
=============================================
Exclusively deploys verified native Z-Image / Lumina2 LoRAs (480-key adaLN/layer architecture):
  - Master: vespera_zit_v5_master.safetensors [0.95, 1.00, 1.05]
  - Anatomy:
      * Z-Hip-Slider.safetensors [0.70, 1.00]
      * Vespera_Body_Physique_v1_ComfyNative.safetensors [0.70, 0.90]
      * Z-Breast-Slider.safetensors [0.60, 0.80]
  - Skin / Texture:
      * skin texture Photorealistic style v4.5.safetensors [0.40, 0.60]
      * OiledSkin_Zit_Turbo_V1.safetensors [0.35, 0.50]
      * ZiTSh4rpD3tails.safetensors [0.40, 0.60]
      * Z-Detail-Slider.safetensors [0.50, 0.80]
  - Lighting / Atmosphere:
      * DarkAtmospheric01_CE_ZIMG_AIT4k.safetensors [0.50, 0.70]
      * light and shadow Portrait.safetensors [0.40, 0.60]
      * dark_dreamcore_style_ZIT_epoch_10.safetensors [0.35, 0.50]
      * None (Baseline Natural Lighting)

Zero foreign Flux or SDXL keys. Every single weight actively affects the DiT.
InsightFace buffalo_l ArcFace validation:
  - Gold: >= 0.25 (staged to native_zit_gold/)
  - Silver: 0.20 - 0.249 (staged to native_zit_silver/)
"""

import os
import sys
import json
import time
import shutil
import random
import urllib.request
import urllib.parse
from pathlib import Path

# Force UTF-8 stdout
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
STAGING_DIR = ZIT_DIR / "Phase2_Curated_Staging"
GOLD_DIR = STAGING_DIR / "native_zit_gold"
SILVER_DIR = STAGING_DIR / "native_zit_silver"
ANCHOR_PATH = ZIT_DIR / "anchor_face_crop.png"
LEADERBOARD_PATH = STAGING_DIR / "NATIVE_ZIT_LEADERBOARD.md"
LEDGER_PATH = STAGING_DIR / "native_zit_results.json"
BASE_WORKFLOW_PATH = PROJECT_ROOT / "scratch" / "sample_prompt_graph.json"

for d in [STAGING_DIR, GOLD_DIR, SILVER_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 100% Native ZIT Safetensors Roster
CANDIDATE_ROSTER = {
    "master_lora": "vespera_zit_v5_master.safetensors",
    "master_weights": [0.95, 1.00, 1.05],
    "anatomy": [
        ("Z-Hip-Slider.safetensors", [0.70, 1.00]),
        ("Vespera_Body_Physique_v1_ComfyNative.safetensors", [0.70, 0.90]),
        ("Z-Breast-Slider.safetensors", [0.60, 0.80])
    ],
    "skin_texture": [
        ("skin texture Photorealistic style v4.5.safetensors", [0.40, 0.60]),
        ("OiledSkin_Zit_Turbo_V1.safetensors", [0.35, 0.50]),
        ("ZiTSh4rpD3tails.safetensors", [0.40, 0.60]),
        ("Z-Detail-Slider.safetensors", [0.50, 0.80])
    ],
    "lighting_mood": [
        ("DarkAtmospheric01_CE_ZIMG_AIT4k.safetensors", [0.50, 0.70]),
        ("light and shadow Portrait.safetensors", [0.40, 0.60]),
        ("dark_dreamcore_style_ZIT_epoch_10.safetensors", [0.35, 0.50]),
        ("None", [0.0])
    ]
}

# Lazy-loaded InsightFace
_FACE_APP = None

def get_face_app():
    global _FACE_APP
    if _FACE_APP is None:
        import cv2
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.30)
        _FACE_APP = app
    return _FACE_APP

def compute_facial_parity(image_path: Path, anchor_path: Path):
    """Computes cosine similarity between target face and canonical anchor face."""
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

def send_comfy_request(endpoint: str, method: str = "GET", data: dict = None, timeout: float = 10.0):
    url = f"{COMFY_BASE_URL}{endpoint}"
    encoded = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def free_comfy_vram():
    try:
        send_comfy_request("/free", method="POST", data={"unload_models": True, "free_memory": True})
        print("⚡ [Hardware] Flushed ComfyUI PyTorch VRAM cache.")
    except Exception:
        pass

def generate_native_pool():
    pool = []
    for master_w in CANDIDATE_ROSTER["master_weights"]:
        for (anat_lora, anat_weights) in CANDIDATE_ROSTER["anatomy"]:
            for anat_w in anat_weights:
                for (skin_lora, skin_weights) in CANDIDATE_ROSTER["skin_texture"]:
                    for skin_w in skin_weights:
                        for (light_lora, light_weights) in CANDIDATE_ROSTER["lighting_mood"]:
                            for light_w in light_weights:
                                pool.append({
                                    "master_lora": CANDIDATE_ROSTER["master_lora"],
                                    "master_weight": master_w,
                                    "anatomy_lora": anat_lora,
                                    "anatomy_weight": anat_w,
                                    "skin_lora": skin_lora,
                                    "skin_weight": skin_w,
                                    "lighting_lora": light_lora,
                                    "lighting_weight": light_w,
                                    "steps": 10,
                                    "cfg": 1.0
                                })
    random.seed(42)
    random.shuffle(pool)
    return pool

def update_leaderboard(results):
    sorted_results = sorted(results, key=lambda x: x.get("parity_score", 0.0), reverse=True)
    gold_count = len([r for r in results if r.get("parity_score", 0) >= 0.25])
    silver_count = len([r for r in results if 0.20 <= r.get("parity_score", 0) < 0.25])

    lines = [
        "# Phase 2 100% Native ZIT LoRA Stack Leaderboard",
        f"**Last Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Stacks Evaluated:** {len(results)}",
        f"**Gold Tier Assets (>= 0.25):** {gold_count} | **Silver Tier (0.20 - 0.249):** {silver_count}",
        "",
        "| Rank | Parity Score | Tier | Master (V5) | Anatomy LoRA | Skin LoRA | Lighting LoRA | Output Asset |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
    ]

    for rank, item in enumerate(sorted_results[:40], 1):
        score = item.get("parity_score", 0.0)
        if score >= 0.25:
            tier_badge = "🥇 GOLD"
        elif score >= 0.20:
            tier_badge = "🥈 SILVER"
        elif score > 0.0:
            tier_badge = "🥉 BRONZE"
        else:
            tier_badge = "❌ NO FACE"

        anat_short = item['anatomy_lora'].replace('.safetensors', '')
        skin_short = item['skin_lora'].replace('.safetensors', '')
        light_short = item['lighting_lora'].replace('.safetensors', '')

        lines.append(
            f"| {rank} | **{score:.4f}** | {tier_badge} | "
            f"V5 ({item['master_weight']}) | "
            f"{anat_short} ({item['anatomy_weight']}) | "
            f"{skin_short} ({item['skin_weight']}) | "
            f"{light_short} ({item['lighting_weight']}) | "
            f"`{item.get('saved_filename', 'N/A')}` |"
        )

    with open(LEADERBOARD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def run_native_optimizer(max_iterations: int = 100):
    if not BASE_WORKFLOW_PATH.exists():
        print(f"[-] Base workflow missing: {BASE_WORKFLOW_PATH}")
        return

    with open(BASE_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        base_workflow = json.load(f)

    results = []
    if LEDGER_PATH.exists():
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
            print(f"[+] Loaded {len(results)} existing records from {LEDGER_PATH.name}")
        except Exception:
            pass

    pool = generate_native_pool()
    print(f"[+] Total native ZIT pool size: {len(pool)} permutations.")
    print(f"[+] Target iterations for this run: {min(max_iterations, len(pool))}")

    eval_count = len(results)
    start_time = time.time()

    for combo in pool:
        if eval_count >= max_iterations:
            print(f"[+] Reached iteration target ({max_iterations}). Halting.")
            break

        combo_sig = (
            f"{combo['master_weight']}_{combo['anatomy_lora']}_{combo['anatomy_weight']}_"
            f"{combo['skin_lora']}_{combo['skin_weight']}_{combo['lighting_lora']}_{combo['lighting_weight']}"
        )
        if any(r.get("signature") == combo_sig for r in results):
            continue

        eval_count += 1
        elapsed_min = (time.time() - start_time) / 60.0
        print(f"\n--- [Native ZIT Stack {eval_count} / {max_iterations}] (Elapsed: {elapsed_min:.1f}m) ---")
        print(f"  • Master: {combo['master_lora']} @ {combo['master_weight']}")
        print(f"  • Anatomy: {combo['anatomy_lora']} @ {combo['anatomy_weight']}")
        print(f"  • Skin: {combo['skin_lora']} @ {combo['skin_weight']}")
        print(f"  • Lighting: {combo['lighting_lora']} @ {combo['lighting_weight']}")

        wf = json.loads(json.dumps(base_workflow))

        # Node 4: DoRA Power LoRA Loader
        dora_inputs = wf["4"]["inputs"]
        dora_inputs["LORA_1"] = {"on": True, "lora": combo["master_lora"], "strength": combo["master_weight"], "strengthTwo": combo["master_weight"]}
        dora_inputs["LORA_2"] = {"on": True, "lora": combo["anatomy_lora"], "strength": combo["anatomy_weight"], "strengthTwo": combo["anatomy_weight"]}
        dora_inputs["LORA_3"] = {"on": True, "lora": combo["skin_lora"], "strength": combo["skin_weight"], "strengthTwo": combo["skin_weight"]}
        
        # Handle lighting LoRA (or None baseline)
        if combo["lighting_lora"] != "None" and combo["lighting_weight"] > 0:
            dora_inputs["LORA_4"] = {"on": True, "lora": combo["lighting_lora"], "strength": combo["lighting_weight"], "strengthTwo": combo["lighting_weight"]}
        else:
            dora_inputs["LORA_4"] = {"on": False, "lora": "None", "strength": 1.0, "strengthTwo": 1.0}
            
        dora_inputs["LORA_5"] = {"on": False, "lora": "None", "strength": 1.0, "strengthTwo": 1.0}

        # Facial prompt anchor on Node 6
        wf["6"]["inputs"]["text_a"] = "vespera, alluring woman, defined facial micro-pores, almond hazel-green eyes, jet-black spiral curls, subtle smirk"

        # Sampling on Node 11
        wf["11"]["inputs"]["steps"] = combo["steps"]
        wf["11"]["inputs"]["cfg"] = combo["cfg"]

        # Filename prefix on Node 13
        prefix_tag = f"native_zit_sweep/nzit_{eval_count:04d}_"
        wf["13"]["inputs"]["text_a"] = prefix_tag
        wf["5"]["inputs"]["master_seed"] = 0

        # Submit prompt
        try:
            res = send_comfy_request("/prompt", method="POST", data={"prompt": wf, "client_id": "native_zit_optimizer"})
            prompt_id = res.get("prompt_id")
            if not prompt_id:
                print(f"  [-] Submission failed: {res}")
                continue
        except Exception as e:
            print(f"  [-] ComfyUI unreachable: {e}")
            time.sleep(5)
            continue

        # Wait for completion
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

        parity, bbox = compute_facial_parity(rendered_file, ANCHOR_PATH)
        
        tier = "NO_FACE"
        if parity >= 0.25:
            tier = "GOLD"
            target_dest = GOLD_DIR / rendered_file.name
            shutil.copy2(rendered_file, target_dest)
            print(f"  >>> 🏆 [GOLD TIER CURATED] Staged to {target_dest.name}")
        elif parity >= 0.20:
            tier = "SILVER"
            target_dest = SILVER_DIR / rendered_file.name
            shutil.copy2(rendered_file, target_dest)
            print(f"  >>> 🥈 [SILVER TIER CURATED] Staged to {target_dest.name}")

        print(f"  >> Biometric Parity: {parity:.4f} [{tier}] (BBox: {bbox})")

        record = dict(combo)
        record.update({
            "signature": combo_sig,
            "run_index": eval_count,
            "prompt_id": prompt_id,
            "parity_score": parity,
            "tier": tier,
            "face_bbox": bbox,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "saved_filename": rendered_file.name
        })
        results.append(record)

        with open(LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        update_leaderboard(results)

        if eval_count % 5 == 0:
            free_comfy_vram()

    print("\n=======================================================")
    print(f"[✓] Native ZIT Sweep Completed. Total Evaluated: {len(results)}")
    print(f"[✓] Staging Directory: {STAGING_DIR}")
    print(f"[✓] Leaderboard: {LEADERBOARD_PATH}")
    print("=======================================================")

if __name__ == "__main__":
    max_runs = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_native_optimizer(max_iterations=max_runs)
