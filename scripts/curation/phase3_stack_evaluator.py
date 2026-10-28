#!/usr/bin/env python3
"""
Antigravity Overdrive :: Phase 3 Autonomous LoRA Stack Evaluator
================================================================
Performs systematic combinatorial sweeps across candidate LoRAs stacked with
Vespera_ZIT_Phase_2_.safetensors using the DoRA Power LoRA Loader.

Evaluates every render using:
  1. Biometric Facial Parity (InsightFace buffalo_l ArcFace cosine similarity vs canonical anchor)
  2. Pure 1-pass latent evaluation (zero inpainting detailers)
  3. Automated curation of top parity candidates to Phase3_Curated_Staging
  4. Real-time markdown leaderboard and JSON ledger
"""

import os
import sys
import json
import time
import shutil
import random
import argparse
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
PROJECT_ROOT = Path(r"D:\AI\Projects\antigravity-overdrive-sync")
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
COMFY_OUTPUT_DIR = COMFY_DIR / "output"
ZIT_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer")
STAGING_DIR = ZIT_DIR / "Phase3_Curated_Staging"
ANCHOR_PATH = Path(r"D:\AI\Projects\ComfyUI\output\dataset_images\vespera_R1_T1_01_Direct_Frontal_Portrait_s0_00001_.png")
LEADERBOARD_PATH = STAGING_DIR / "LEADERBOARD.md"
LEDGER_PATH = STAGING_DIR / "sweep_results.json"
BASE_WORKFLOW_PATH = PROJECT_ROOT / "scratch" / "sample_prompt_graph.json"

STAGING_DIR.mkdir(parents=True, exist_ok=True)

# Master LoRA for Phase 3
MASTER_LORA = "Vespera_ZIT_Phase_2_.safetensors"
MASTER_WEIGHTS = [1.00]

# Candidate Roster (Curated for Phase 3 parity and fidelity)
CANDIDATE_ROSTER = {
    "anatomy": [
        ("Z-Hip-Slider.safetensors", [0.85, 1.05]),
        ("ZIB_SkinnyVoluptousSlider_v5.1.safetensors", [0.60, 0.85]),
        ("zit_thickness.safetensors", [0.75, 1.00]),
    ],
    "skin_texture": [
        ("Z-Detail-Slider.safetensors", [0.35, 0.55]),
        ("ZiTSh4rpD3tails.safetensors", [0.30, 0.45]),
        ("ZIT_photolab_v2.safetensors", [0.25, 0.40]),
        ("skin texture Photorealistic style v4.5.safetensors", [0.40, 0.60]),
    ],
    "lighting_mood": [
        ("light and shadow Portrait.safetensors", [0.25, 0.40]),
        ("zy_CinematicShot_zit.safetensors", [0.25, 0.35]),
        ("dark_dreamcore_style_ZIT_epoch_10.safetensors", [0.25, 0.35]),
        ("Chiaroscuro zib v1.safetensors", [0.30, 0.45]),
        ("Z-Image Turbo Radiant v2.0.safetensors", [0.30, 0.45]),
    ]
}

# Lazy-loaded InsightFace & Cached Anchor Embedding
_FACE_APP = None
_ANCHOR_EMB = None

def get_face_app():
    global _FACE_APP
    if _FACE_APP is None:
        import cv2
        from insightface.app import FaceAnalysis
        print("  [AI] Initializing InsightFace buffalo_l on CPU...")
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.20)
        _FACE_APP = app
    return _FACE_APP

def get_anchor_embedding():
    global _ANCHOR_EMB
    if _ANCHOR_EMB is None:
        import cv2
        app = get_face_app()
        img_anchor = cv2.imread(str(ANCHOR_PATH))
        if img_anchor is None:
            raise FileNotFoundError(f"Canonical anchor not found at {ANCHOR_PATH}")
        faces_a = app.get(img_anchor)
        if not faces_a:
            raise RuntimeError(f"No face detected in canonical anchor: {ANCHOR_PATH.name}")
        faces_a = sorted(faces_a, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)
        _ANCHOR_EMB = faces_a[0].normed_embedding
        print(f"  [AI] Loaded canonical anchor embedding from: {ANCHOR_PATH.name}")
    return _ANCHOR_EMB

def compute_facial_parity(image_path: Path, anchor_path: Path = None) -> float:
    """Computes cosine similarity between target face and canonical anchor face."""
    import cv2
    import numpy as np
    try:
        app = get_face_app()
        emb_a = get_anchor_embedding()
        img_target = cv2.imread(str(image_path))
        if img_target is None:
            return 0.0

        faces_t = app.get(img_target)
        if not faces_t:
            return 0.0

        faces_t = sorted(faces_t, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)
        emb_t = faces_t[0].normed_embedding

        return float(np.dot(emb_t, emb_a))
    except Exception as e:
        print(f"[-] Parity calculation error: {e}")
        return 0.0

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

def generate_combination_pool():
    """Generates a structured combinatorial pool across candidate slots."""
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
        "# Phase 3 LoRA Stack Leaderboard (Vespera_ZIT_Phase_2_)",
        f"**Last Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Stacks Evaluated:** {len(results)}",
        f"**Golden Candidates Curated:** {len([r for r in results if r.get('parity_score', 0) >= 0.72])}",
        "",
        "| Rank | Parity Score | Rating | Master LoRA (V6) | Anatomy LoRA | Skin/Texture LoRA | Lighting/Mood LoRA | Output Asset |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
    ]

    for rank, r in enumerate(sorted_results[:25], 1):
        score = r.get("parity_score", 0.0)
        rating = "🌟 GOLDEN" if score >= 0.72 else ("✅ PASS" if score >= 0.65 else ("⚠️ DRIFT" if score >= 0.55 else "❌ FAIL"))
        m_info = f"V6 ({r['master_weight']})"
        a_info = f"{Path(r['anatomy_lora']).stem} ({r['anatomy_weight']})"
        s_info = f"{Path(r['skin_lora']).stem} ({r['skin_weight']})"
        l_info = f"{Path(r['lighting_lora']).stem} ({r['lighting_weight']})"
        asset_name = r.get("saved_filename", "N/A")
        lines.append(f"| {rank} | **{score:.4f}** | {rating} | {m_info} | {a_info} | {s_info} | {l_info} | `{asset_name}` |")

    with open(LEADERBOARD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main():
    parser = argparse.ArgumentParser(description="Phase 3 Autonomous LoRA Stack Evaluator")
    parser.add_argument("--max-evals", type=int, default=0, help="Maximum stacks to evaluate (0 for unlimited)")
    parser.add_argument("--clean", action="store_true", help="Start fresh without loading existing ledger")
    args = parser.parse_args()

    print("=" * 80)
    print("🚀 Antigravity Overdrive :: Phase 3 Autonomous LoRA Stack Evaluator")
    print(f"Master LoRA Anchor : {MASTER_LORA}")
    print(f"Target Staging     : {STAGING_DIR}")
    print(f"Canonical Anchor   : {ANCHOR_PATH.name}")
    print(f"Leaderboard        : {LEADERBOARD_PATH}")
    print("=" * 80)

    if not BASE_WORKFLOW_PATH.is_file():
        print(f"[-] Base workflow not found at {BASE_WORKFLOW_PATH}")
        sys.exit(1)

    with open(BASE_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        base_workflow = json.load(f)

    results = []
    if not args.clean and LEDGER_PATH.is_file():
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
            print(f"[+] Loaded {len(results)} previous evaluations from ledger.")
        except Exception:
            pass

    pool = generate_combination_pool()
    print(f"[+] Generated combinatorial pool of {len(pool)} total stack permutations.")

    eval_count = len(results)
    start_time = time.time()
    completed_this_session = 0

    for idx, combo in enumerate(pool):
        if args.max_evals > 0 and completed_this_session >= args.max_evals:
            print(f"[+] Reached session limit of {args.max_evals} evaluations.")
            break

        combo_sig = (
            f"{combo['master_weight']}_{combo['anatomy_lora']}_{combo['anatomy_weight']}_"
            f"{combo['skin_lora']}_{combo['skin_weight']}_{combo['lighting_lora']}_{combo['lighting_weight']}"
        )
        if any(r.get("signature") == combo_sig for r in results):
            continue

        eval_count += 1
        completed_this_session += 1
        elapsed_min = (time.time() - start_time) / 60.0
        print(f"\n--- [Stack {eval_count} / {len(pool)}] (Session: {completed_this_session}) (Elapsed: {elapsed_min:.1f}m) ---")
        print(f"  • Master:   {combo['master_lora']} @ {combo['master_weight']}")
        print(f"  • Anatomy:  {combo['anatomy_lora']} @ {combo['anatomy_weight']}")
        print(f"  • Skin:     {combo['skin_lora']} @ {combo['skin_weight']}")
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

        # FlowMatch scheduler & calibrated sampling
        wf["11"]["inputs"]["scheduler"] = "FlowMatchEulerDiscreteScheduler"
        wf["11"]["inputs"]["steps"] = 10
        wf["11"]["inputs"]["cfg"] = 1.0

        # Inject rich biometric prompt core into Node 6 text_a
        wf["6"]["inputs"]["text_a"] = (
            "vespera, alluring woman of French-Levantine and Mediterranean heritage with athletic narrow cinched waist, "
            "wide hips with full perfectly rounded gluteal contours, toned thighs, and natural firm high-set modest bust, "
            "unblemished luminous warm olive skin retaining photorealistic micro-pores, skin texture, and golden undertones with specular highlights on cheekbones and collarbones, "
            "sculpted facial structure with high cheekbones and soft-tapered button nose, captivating deep hazel-green almond-shaped eyes with soft-smudged smoky eyeliner, "
            "full soft satin lips with subtle natural moisture and tiny beauty mark beside upper-left lip corner, voluminous jet-black 3B/3C spiral corkscrew curls with fine interwoven electric-indigo highlights framing face, "
            "subtle asymmetrical half-smirk"
        )

        # Filename prefix
        prefix_tag = f"phase3_lora_sweep/run_{eval_count:04d}_"
        wf["13"]["inputs"]["text_a"] = prefix_tag
        wf["5"]["inputs"]["master_seed"] = 0  # Standard benchmark pose

        # Submit to ComfyUI
        try:
            res = send_comfy_request("/prompt", method="POST", data={"prompt": wf, "client_id": "phase3_evaluator"})
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
            time.sleep(1.0)

        if not rendered_file or not rendered_file.is_file():
            print("  [-] Render timed out or output not found.")
            continue

        # Compute Facial Parity Score
        parity_score = compute_facial_parity(rendered_file, ANCHOR_PATH)
        rating = "🌟 GOLDEN" if parity_score >= 0.72 else ("✅ PASS" if parity_score >= 0.65 else ("⚠️ DRIFT" if parity_score >= 0.55 else "❌ FAIL"))
        print(f"  >> Biometric Parity: {parity_score:.4f} [{rating}]")

        record = dict(combo)
        record["signature"] = combo_sig
        record["run_index"] = eval_count
        record["prompt_id"] = prompt_id
        record["parity_score"] = parity_score
        record["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        record["saved_filename"] = rendered_file.name

        # If high-parity candidate, stage for Master Phase 3
        if parity_score >= 0.72:
            staged_name = f"phase3_golden_score_{int(parity_score*1000):04d}_run_{eval_count:04d}_{rendered_file.name}"
            staged_path = STAGING_DIR / staged_name
            shutil.copy2(rendered_file, staged_path)
            
            with open(staged_path.with_suffix(".json"), "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
            print(f"  🏆 [CURATED] Staged golden candidate to: {staged_name}")

        results.append(record)

        # Update live ledger & leaderboard
        with open(LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        update_leaderboard(results)

        # Periodic VRAM flush
        if eval_count % 5 == 0:
            free_comfy_vram()

        time.sleep(0.5)

    print(f"\n[+] Evaluator run completed. {completed_this_session} stacks evaluated.")
    print(f"[+] Review leaderboard at: {LEADERBOARD_PATH}")

if __name__ == "__main__":
    main()
