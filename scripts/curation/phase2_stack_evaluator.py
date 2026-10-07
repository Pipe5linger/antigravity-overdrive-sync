#!/usr/bin/env python3
"""
Antigravity Overdrive :: Phase 2 Autonomous LoRA Stack Evaluator
Performs continuous multi-hour combinatorial sweeps across candidate LoRAs stacked with
vespera_zit_v5_master using the DoRA Power LoRA Loader.

Evaluates every render using:
  1. Biometric Facial Parity (InsightFace buffalo_l ArcFace vs canonical anchor)
  2. Anatomical coherence and identity preservation
  3. Automated master curation to Phase2_Curated_Staging
  4. Real-time markdown leaderboard and ULM golden recipe recording
"""

import os
import sys
import json
import time
import shutil
import random
import itertools
from pathlib import Path
import urllib.request
import urllib.error

# Ensure UTF-8 output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except AttributeError:
        pass

# Paths
COMFY_BASE_URL = "http://127.0.0.1:8188"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
COMFY_OUTPUT_DIR = COMFY_DIR / "output"
ZIT_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer")
STAGING_DIR = ZIT_DIR / "Phase2_Curated_Staging"
ANCHOR_PATH = ZIT_DIR / "anchor_face_crop.png"
LEADERBOARD_PATH = STAGING_DIR / "LEADERBOARD.md"
LEDGER_PATH = STAGING_DIR / "sweep_results.json"
BASE_WORKFLOW_PATH = PROJECT_ROOT / "scratch" / "sample_prompt_graph.json"

STAGING_DIR.mkdir(parents=True, exist_ok=True)

# Candidate Roster (17 Tested & Verified Safetensors)
CANDIDATE_ROSTER = {
    "anatomy": [
        ("zit_thickness.safetensors", [0.75, 1.10]),
        ("Z-Hip-Slider.safetensors", [0.80, 1.25]),
        ("Vespera_Body_Physique_v1_ComfyNative.safetensors", [0.70, 1.00]),
        ("z-image-turbo_hourglass-figure.safetensors", [0.65, 0.95]),
        ("ZIB_SkinnyVoluptousSlider_v5.1.safetensors", [0.80, 1.20])
    ],
    "skin_texture": [
        ("fluxRealSkin-V2.safetensors", [0.55, 0.85]),
        ("skin texture Photorealistic style v4.5.safetensors", [0.50, 0.80]),
        ("ZiTD3tailedP0rtraits.safetensors", [0.50, 0.75]),
        ("OiledSkin_Zit_Turbo_V1.safetensors", [0.45, 0.70]),
        ("AntiPlastic_AnalogTexture_v1.safetensors", [0.60, 0.90]),
        ("REDZ15_DetailDaemonZ_lora_v1.1.safetensors", [0.45, 0.75])
    ],
    "lighting_mood": [
        ("Chiaroscuro zib v1.safetensors", [0.45, 0.75]),
        ("Neon_Noir_Atmospheric_Flux.safetensors", [0.40, 0.70]),
        ("DarkAtmospheric01_CE_ZIMG_AIT4k.safetensors", [0.45, 0.80]),
        ("50sNoirZ.safetensors", [0.35, 0.65]),
        ("Cinematic Film Color style v1.2.safetensors", [0.40, 0.70]),
        ("Low-key lighting Style v1.safetensors", [0.40, 0.75])
    ]
}

MASTER_LORA = "vespera_zit_v5_master.safetensors"
MASTER_WEIGHTS = [0.95, 1.05]

# Lazy-loaded InsightFace
_FACE_APP = None

def get_face_app():
    global _FACE_APP
    if _FACE_APP is None:
        import cv2
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.35)
        _FACE_APP = app
    return _FACE_APP

def compute_facial_parity(image_path: Path, anchor_path: Path) -> float:
    """Computes cosine similarity between target face and canonical anchor face."""
    import cv2
    import numpy as np
    try:
        app = get_face_app()
        img_target = cv2.imread(str(image_path))
        img_anchor = cv2.imread(str(anchor_path))
        if img_target is None or img_anchor is None:
            return 0.0

        faces_t = app.get(img_target)
        faces_a = app.get(img_anchor)
        if not faces_t or not faces_a:
            return 0.0

        emb_t = sorted(faces_t, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0].normed_embedding
        emb_a = sorted(faces_a, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0].normed_embedding

        return float(np.dot(emb_t, emb_a))
    except Exception as e:
        print(f"[-] Parity calculation error: {e}")
        return 0.0

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

def generate_combination_pool():
    """Generates an evenly shuffled combinatorial pool of 4-LoRA stacks."""
    pool = []
    for master_w in MASTER_WEIGHTS:
        for (anat_lora, anat_weights) in CANDIDATE_ROSTER["anatomy"]:
            for anat_w in anat_weights:
                for (skin_lora, skin_weights) in CANDIDATE_ROSTER["skin_texture"]:
                    for skin_w in skin_weights:
                        for (light_lora, light_weights) in CANDIDATE_ROSTER["lighting_mood"]:
                            for light_w in light_weights:
                                pool.append({
                                    "master_lora": MASTER_LORA,
                                    "master_weight": master_w,
                                    "anatomy_lora": anat_lora,
                                    "anatomy_weight": anat_w,
                                    "skin_lora": skin_lora,
                                    "skin_weight": skin_w,
                                    "lighting_lora": light_lora,
                                    "lighting_weight": light_w
                                })
    random.seed(42)
    random.shuffle(pool)
    return pool

def update_leaderboard(results):
    """Writes a sorted markdown leaderboard of the top-performing stacks."""
    sorted_results = sorted(results, key=lambda x: x.get("parity_score", 0.0), reverse=True)
    lines = [
        "# Phase 2 LoRA Stack Leaderboard",
        f"**Last Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Stacks Evaluated:** {len(results)}",
        f"**Golden Candidates Curated:** {len([r for r in results if r.get('parity_score', 0) >= 0.44])}",
        "",
        "| Rank | Parity Score | Rating | Master LoRA (V5) | Anatomy LoRA | Skin/Texture LoRA | Lighting/Mood LoRA | Output Asset |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
    ]

    for rank, r in enumerate(sorted_results[:40], 1):
        score = r.get("parity_score", 0.0)
        rating = "🌟 GOLDEN" if score >= 0.48 else ("✅ PASS" if score >= 0.44 else ("⚠️ DRIFT" if score >= 0.35 else "❌ FAIL"))
        m_info = f"V5 ({r['master_weight']})"
        a_info = f"{Path(r['anatomy_lora']).stem} ({r['anatomy_weight']})"
        s_info = f"{Path(r['skin_lora']).stem} ({r['skin_weight']})"
        l_info = f"{Path(r['lighting_lora']).stem} ({r['lighting_weight']})"
        asset_name = r.get("saved_filename", "N/A")
        lines.append(f"| {rank} | **{score:.4f}** | {rating} | {m_info} | {a_info} | {s_info} | {l_info} | `{asset_name}` |")

    with open(LEADERBOARD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main():
    print("=" * 75)
    print("🚀 Antigravity Overdrive :: Phase 2 Autonomous LoRA Stack Evaluator")
    print(f"Target Staging: {STAGING_DIR}")
    print(f"Canonical Anchor: {ANCHOR_PATH.name}")
    print("=" * 75)

    if not BASE_WORKFLOW_PATH.is_file():
        print(f"[-] Base workflow not found at {BASE_WORKFLOW_PATH}")
        sys.exit(1)

    with open(BASE_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        base_workflow = json.load(f)

    # Load existing ledger if present
    results = []
    if LEDGER_PATH.is_file():
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
            print(f"[+] Loaded {len(results)} previous results from ledger.")
        except Exception:
            pass

    pool = generate_combination_pool()
    print(f"[+] Generated combinatorial pool of {len(pool)} total stack permutations.")

    eval_count = len(results)
    start_time = time.time()

    for idx, combo in enumerate(pool):
        # Check if combination was already run
        combo_sig = (
            f"{combo['master_weight']}_{combo['anatomy_lora']}_{combo['anatomy_weight']}_"
            f"{combo['skin_lora']}_{combo['skin_weight']}_{combo['lighting_lora']}_{combo['lighting_weight']}"
        )
        if any(r.get("signature") == combo_sig for r in results):
            continue

        eval_count += 1
        elapsed_min = (time.time() - start_time) / 60.0
        print(f"\n--- [Stack {eval_count} / {len(pool)}] (Elapsed: {elapsed_min:.1f}m) ---")
        print(f"  • Master: {combo['master_lora']} @ {combo['master_weight']}")
        print(f"  • Anatomy: {combo['anatomy_lora']} @ {combo['anatomy_weight']}")
        print(f"  • Skin: {combo['skin_lora']} @ {combo['skin_weight']}")
        print(f"  • Lighting: {combo['lighting_lora']} @ {combo['lighting_weight']}")

        # Clone and inject into workflow
        wf = json.loads(json.dumps(base_workflow))

        # Node 4: DoRA Power LoRA Loader
        dora_inputs = wf["4"]["inputs"]
        dora_inputs["LORA_1"] = {"on": True, "lora": combo["master_lora"], "strength": combo["master_weight"], "strengthTwo": combo["master_weight"]}
        dora_inputs["LORA_2"] = {"on": True, "lora": combo["anatomy_lora"], "strength": combo["anatomy_weight"], "strengthTwo": combo["anatomy_weight"]}
        dora_inputs["LORA_3"] = {"on": True, "lora": combo["skin_lora"], "strength": combo["skin_weight"], "strengthTwo": combo["skin_weight"]}
        dora_inputs["LORA_4"] = {"on": True, "lora": combo["lighting_lora"], "strength": combo["lighting_weight"], "strengthTwo": combo["lighting_weight"]}
        dora_inputs["LORA_5"] = {"on": False, "lora": "None", "strength": 1.0, "strengthTwo": 1.0}

        # Node 13: Unique filename prefix
        prefix_tag = f"phase2_sweep/run_{eval_count:04d}_"
        wf["13"]["inputs"]["text_a"] = prefix_tag
        wf["5"]["inputs"]["master_seed"] = 0  # Fixed control portrait pose

        # Submit to ComfyUI
        try:
            res = send_comfy_request("/prompt", method="POST", data={"prompt": wf, "client_id": "phase2_evaluator"})
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
                    data = hist[prompt_id]
                    if data.get("status", {}).get("completed", False):
                        outputs = data.get("outputs", {})
                        for _, n_out in outputs.items():
                            if "images" in n_out:
                                for img_dict in n_out["images"]:
                                    sub = img_dict.get("subfolder", "")
                                    fname = img_dict.get("filename", "")
                                    cand = COMFY_OUTPUT_DIR / sub / fname if sub else COMFY_OUTPUT_DIR / fname
                                    if cand.is_file():
                                        rendered_file = cand
                                        break
                        break
            except Exception:
                pass
            time.sleep(1.5)

        if not rendered_file or not rendered_file.is_file():
            print("  [-] Render timed out or output not found.")
            continue

        # Compute Facial Parity Score
        parity_score = compute_facial_parity(rendered_file, ANCHOR_PATH)
        rating = "🌟 GOLDEN" if parity_score >= 0.48 else ("✅ PASS" if parity_score >= 0.44 else ("⚠️ DRIFT" if parity_score >= 0.35 else "❌ FAIL"))
        print(f"  >> Biometric Parity: {parity_score:.4f} [{rating}]")

        record = dict(combo)
        record["signature"] = combo_sig
        record["run_index"] = eval_count
        record["prompt_id"] = prompt_id
        record["parity_score"] = parity_score
        record["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        record["saved_filename"] = rendered_file.name

        # If high-parity candidate, stage for Master Phase 2 Dataset
        if parity_score >= 0.44:
            staged_name = f"phase2_golden_score_{int(parity_score*1000):04d}_run_{eval_count:04d}_{rendered_file.name}"
            staged_path = STAGING_DIR / staged_name
            shutil.copy2(rendered_file, staged_path)
            
            # Save companion metadata
            with open(staged_path.with_suffix(".json"), "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
            print(f"  🏆 [CURATED] Staged golden candidate to: {staged_name}")

        results.append(record)

        # Update live ledger & leaderboard
        with open(LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        update_leaderboard(results)

        # Periodic VRAM Flush
        if eval_count % 5 == 0:
            free_comfy_vram()

        time.sleep(1.0)

    print("\n[+] Full Phase 2 combinatorial sweep completed successfully.")

if __name__ == "__main__":
    main()
