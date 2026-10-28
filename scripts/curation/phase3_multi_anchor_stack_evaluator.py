"""
Phase 3 Multi-Anchor Hierarchical LoRA Stack Evaluator
======================================================
Tests combinatorial LoRA stacks across wide exploratory strength boundaries,
evaluating facial parity against the multi-anchor biometric suite:
1. Frontal: s0 (Canonical Frontal Anchor)
2. 3/4 Profile: s482 (Three-Quarter Profile Right)
3. 90° Profile: s5 (Full Profile Right Silhouette)

Features:
- Two-Tier Exploration: Broad/Liberal exploration -> Narrow/Tight calibration.
- Multi-Anchor Weighted Parity Scoring:
    Parity = 0.50 * Frontal + 0.30 * Profile_34 + 0.20 * Profile_90
- Pure ZIT Native Latent Pass (No Detailer Inpainting).
- Automatic Live Leaderboard & Stage Curator.
"""

import sys
import os
import time
import json
import random
import shutil
import urllib.request
import argparse
from pathlib import Path
import cv2
import numpy as np

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

# Paths
COMFY_BASE_URL = "http://127.0.0.1:8188"
PROJECT_ROOT = Path(r"D:\AI\Projects\antigravity-overdrive-sync")
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
COMFY_OUTPUT_DIR = COMFY_DIR / "output"
ZIT_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer")
STAGING_DIR = ZIT_DIR / "Phase3_Curated_Staging"
BASE_WORKFLOW_PATH = PROJECT_ROOT / "scratch" / "sample_prompt_graph.json"

LEADERBOARD_PATH = STAGING_DIR / "LEADERBOARD_MULTI_ANCHOR.md"
LEDGER_PATH = STAGING_DIR / "sweep_results_multi_anchor.json"

STAGING_DIR.mkdir(parents=True, exist_ok=True)

# Reference Anchors Specified by User (Migrated from ZIT_LoRA_Trainer to ai-toolkit/vespera_anchors)
ANCHOR_VAULT = Path(r"D:\AI\Projects\ai-toolkit\vespera_anchors")
ANCHOR_FRONTAL_PATH = ANCHOR_VAULT / "anchor_frontal.png"
ANCHOR_PROFILE_90_PATH = ANCHOR_VAULT / "anchor_profile_right.png"
ANCHOR_PROFILE_34_PATH = ANCHOR_VAULT / "anchor_profile_left.png"

# Master LoRA
MASTER_LORA = "Vespera_ZIT_Phase_2_.safetensors"

# Broad Liberal Candidate Roster (Phase 1: Exploration)
BROAD_ROSTER = {
    "master_weights": [0.85, 1.00, 1.15],
    "anatomy": [
        ("Z-Hip-Slider.safetensors", [0.70, 0.95, 1.20]),
        ("ZIB_SkinnyVoluptousSlider_v5.1.safetensors", [0.50, 0.70, 0.90]),
        ("zit_thickness.safetensors", [0.60, 0.85, 1.10]),
        ("None", [0.0]),
    ],
    "skin_texture": [
        ("Z-Detail-Slider.safetensors", [0.20, 0.35, 0.55]),
        ("ZiTSh4rpD3tails.safetensors", [0.25, 0.40]),
        ("skin texture Photorealistic style v4.5.safetensors", [0.30, 0.50]),
        ("AntiPlastic_AnalogTexture_v1.safetensors", [0.30, 0.50]),
        ("None", [0.0]),
    ],
    "lighting_mood": [
        ("Chiaroscuro zib v1.safetensors", [0.25, 0.40, 0.55]),
        ("dark_dreamcore_style_ZIT_epoch_10.safetensors", [0.20, 0.35]),
        ("light and shadow Portrait.safetensors", [0.25, 0.40]),
        ("Low-key lighting Style v1.safetensors", [0.25, 0.40]),
        ("None", [0.0]),
    ]
}

# Narrow Focused Candidate Roster (Phase 2: Fine-Tuning Calibration)
NARROW_ROSTER = {
    "master_weights": [1.00],
    "anatomy": [
        ("Z-Hip-Slider.safetensors", [0.85, 0.95, 1.05]),
        ("ZIB_SkinnyVoluptousSlider_v5.1.safetensors", [0.60, 0.70]),
    ],
    "skin_texture": [
        ("Z-Detail-Slider.safetensors", [0.30, 0.35, 0.40]),
        ("skin texture Photorealistic style v4.5.safetensors", [0.35, 0.45]),
    ],
    "lighting_mood": [
        ("Chiaroscuro zib v1.safetensors", [0.35, 0.40, 0.45]),
        ("dark_dreamcore_style_ZIT_epoch_10.safetensors", [0.25, 0.30]),
    ]
}

_FACE_APP = None
_ANCHOR_EMBS = {}

def get_face_app():
    global _FACE_APP
    if _FACE_APP is None:
        from insightface.app import FaceAnalysis
        print("  [AI] Initializing InsightFace buffalo_l on CPU...")
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.20)
        _FACE_APP = app
    return _FACE_APP

def load_face_embedding(img_path: Path):
    app = get_face_app()
    img = cv2.imread(str(img_path))
    if img is None:
        return None
    faces = app.get(img)
    if not faces:
        return None
    largest_face = sorted(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0]
    return largest_face.normed_embedding

def init_anchors():
    global _ANCHOR_EMBS
    if not _ANCHOR_EMBS:
        print("[+] Loading Multi-Anchor Reference Biometrics...")
        f_emb = load_face_embedding(ANCHOR_FRONTAL_PATH)
        p34_emb = load_face_embedding(ANCHOR_PROFILE_34_PATH)
        p90_emb = load_face_embedding(ANCHOR_PROFILE_90_PATH)

        if f_emb is None:
            raise FileNotFoundError(f"Could not extract face from Frontal Anchor: {ANCHOR_FRONTAL_PATH}")
        if p34_emb is None:
            raise FileNotFoundError(f"Could not extract face from 3/4 Profile Anchor: {ANCHOR_PROFILE_34_PATH}")
        if p90_emb is None:
            raise FileNotFoundError(f"Could not extract face from 90° Profile Anchor: {ANCHOR_PROFILE_90_PATH}")

        _ANCHOR_EMBS = {
            "frontal": f_emb,
            "profile_34": p34_emb,
            "profile_90": p90_emb,
        }
        print("  ✓ Frontal Anchor Loaded:", ANCHOR_FRONTAL_PATH.name)
        print("  ✓ 3/4 Profile Anchor Loaded:", ANCHOR_PROFILE_34_PATH.name)
        print("  ✓ 90° Profile Anchor Loaded:", ANCHOR_PROFILE_90_PATH.name)

def compute_multi_anchor_parity(target_path: Path) -> dict:
    """Computes weighted multi-anchor parity."""
    app = get_face_app()
    img = cv2.imread(str(target_path))
    if img is None:
        return {"composite": 0.0, "frontal": 0.0, "p34": 0.0, "p90": 0.0}

    faces = app.get(img)
    if not faces:
        return {"composite": 0.0, "frontal": 0.0, "p34": 0.0, "p90": 0.0}

    target_emb = sorted(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0].normed_embedding

    sim_frontal = float(np.dot(target_emb, _ANCHOR_EMBS["frontal"]))
    sim_p34 = float(np.dot(target_emb, _ANCHOR_EMBS["profile_34"]))
    sim_p90 = float(np.dot(target_emb, _ANCHOR_EMBS["profile_90"]))

    # Composite weighted formula: 50% frontal match, 30% 3/4 volume, 20% profile jawline
    composite = (0.50 * sim_frontal) + (0.30 * sim_p34) + (0.20 * sim_p90)

    return {
        "composite": composite,
        "frontal": sim_frontal,
        "p34": sim_p34,
        "p90": sim_p90,
    }

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

def generate_combination_pool(roster: dict):
    pool = []
    for master_w in roster["master_weights"]:
        for (anat_lora, anat_weights) in roster["anatomy"]:
            for anat_w in anat_weights:
                for (skin_lora, skin_weights) in roster["skin_texture"]:
                    for skin_w in skin_weights:
                        for (light_lora, light_weights) in roster["lighting_mood"]:
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
    sorted_results = sorted(results, key=lambda x: x.get("parity_composite", 0.0), reverse=True)
    lines = [
        "# Phase 3 Multi-Anchor LoRA Stack Leaderboard",
        f"**Last Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Stacks Evaluated:** {len(results)}",
        f"**Golden Candidates Curated:** {len([r for r in results if r.get('parity_composite', 0) >= 0.70])}",
        "",
        "| Rank | Composite | Frontal | 3/4 | 90° | Master | Anatomy LoRA | Skin/Texture | Lighting/Mood | Output Asset |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for rank, r in enumerate(sorted_results[:50], 1):
        c_score = r.get("parity_composite", 0.0)
        f_score = r.get("parity_frontal", 0.0)
        p34_score = r.get("parity_p34", 0.0)
        p90_score = r.get("parity_p90", 0.0)
        
        m_info = f"V6 ({r['master_weight']})"
        a_info = f"{Path(r['anatomy_lora']).stem} ({r['anatomy_weight']})" if r['anatomy_lora'] != "None" else "None"
        s_info = f"{Path(r['skin_lora']).stem} ({r['skin_weight']})" if r['skin_lora'] != "None" else "None"
        l_info = f"{Path(r['lighting_lora']).stem} ({r['lighting_weight']})" if r['lighting_lora'] != "None" else "None"
        asset_name = r.get("saved_filename", "N/A")
        
        lines.append(f"| {rank} | **{c_score:.4f}** | {f_score:.4f} | {p34_score:.4f} | {p90_score:.4f} | {m_info} | {a_info} | {s_info} | {l_info} | `{asset_name}` |")

    with open(LEADERBOARD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main():
    parser = argparse.ArgumentParser(description="Multi-Anchor Hierarchical LoRA Stack Evaluator")
    parser.add_argument("--mode", choices=["broad", "narrow"], default="broad", help="Exploration mode: broad or narrow")
    parser.add_argument("--max-evals", type=int, default=0, help="Max evaluations to run this session (0 for unlimited)")
    parser.add_argument("--target-total", type=int, default=1000, help="Target total evaluated stacks across all runs (default: 1000)")
    parser.add_argument("--clean", action="store_true", help="Start fresh without loading existing ledger")
    args = parser.parse_args()

    init_anchors()

    roster = BROAD_ROSTER if args.mode == "broad" else NARROW_ROSTER
    pool = generate_combination_pool(roster)

    print("=" * 80)
    print(f"🚀 Antigravity Overdrive :: Multi-Anchor LoRA Stack Evaluator [{args.mode.upper()} MODE]")
    print(f"Total Combinatorial Candidates : {len(pool)}")
    print(f"Target Staging Directory       : {STAGING_DIR}")
    print(f"Leaderboard Output             : {LEADERBOARD_PATH}")
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
            print(f"[+] Loaded {len(results)} existing evaluations from ledger.")
        except Exception:
            results = []

    evaluated_signatures = {r.get("signature") for r in results if "signature" in r}

    eval_count = len(results)
    completed_this_session = 0
    start_time = time.time()

    for combo in pool:
        if args.target_total > 0 and len(results) >= args.target_total:
            print(f"\n[!] 🎯 Reached target total goal of {args.target_total} evaluated stacks! Halting.")
            break

        if args.max_evals > 0 and completed_this_session >= args.max_evals:
            print(f"\n[!] Reached session evaluation limit of {args.max_evals}. Halting.")
            break

        combo_sig = f"{combo['master_lora']}_{combo['master_weight']}_{combo['anatomy_lora']}_{combo['anatomy_weight']}_{combo['skin_lora']}_{combo['skin_weight']}_{combo['lighting_lora']}_{combo['lighting_weight']}"
        if combo_sig in evaluated_signatures:
            continue

        eval_count += 1
        completed_this_session += 1
        elapsed_min = (time.time() - start_time) / 60.0
        print(f"\n--- [Stack {eval_count} / {len(pool)}] (Session: {completed_this_session}) (Elapsed: {elapsed_min:.1f}m) ---")
        print(f"  • Master:   {combo['master_lora']} @ {combo['master_weight']}")
        print(f"  • Anatomy:  {combo['anatomy_lora']} @ {combo['anatomy_weight']}")
        print(f"  • Skin:     {combo['skin_lora']} @ {combo['skin_weight']}")
        print(f"  • Lighting: {combo['lighting_lora']} @ {combo['lighting_weight']}")

        # Clone and configure workflow
        wf = json.loads(json.dumps(base_workflow))

        # Node 4: DoRA Power LoRA Loader
        dora_inputs = wf["4"]["inputs"]
        dora_inputs["LORA_1"] = {"on": True, "lora": combo["master_lora"], "strength": combo["master_weight"], "strengthTwo": combo["master_weight"]}
        
        dora_inputs["LORA_2"] = {
            "on": combo["anatomy_lora"] != "None",
            "lora": combo["anatomy_lora"] if combo["anatomy_lora"] != "None" else "None",
            "strength": combo["anatomy_weight"],
            "strengthTwo": combo["anatomy_weight"]
        }
        dora_inputs["LORA_3"] = {
            "on": combo["skin_lora"] != "None",
            "lora": combo["skin_lora"] if combo["skin_lora"] != "None" else "None",
            "strength": combo["skin_weight"],
            "strengthTwo": combo["skin_weight"]
        }
        dora_inputs["LORA_4"] = {
            "on": combo["lighting_lora"] != "None",
            "lora": combo["lighting_lora"] if combo["lighting_lora"] != "None" else "None",
            "strength": combo["lighting_weight"],
            "strengthTwo": combo["lighting_weight"]
        }
        dora_inputs["LORA_5"] = {"on": False, "lora": "None", "strength": 1.0, "strengthTwo": 1.0}

        # FlowMatch scheduler & calibrated sampling (12 steps for pure acutance)
        wf["11"]["inputs"]["scheduler"] = "FlowMatchEulerDiscreteScheduler"
        wf["11"]["inputs"]["steps"] = 12
        wf["11"]["inputs"]["cfg"] = 1.0

        # Inject clean anatomical prompt into Node 6 text_a
        wf["6"]["inputs"]["text_a"] = (
            "vespera, alluring woman of French-Levantine and Mediterranean heritage with athletic narrow cinched waist, "
            "wide hips with full perfectly rounded gluteal contours, toned thighs, and natural firm high-set modest bust, "
            "unblemished luminous warm olive skin retaining photorealistic micro-pores, skin texture, and golden undertones with soft specular highlights on cheekbones and collarbones, "
            "sculpted facial structure with high cheekbones and soft-tapered button nose, captivating deep-set almond-shaped hazel-green eyes with glowing amber-gold striations, "
            "clean natural lash line, sharp iris striations, natural eye catchlights, delicate natural lash shadow, natural dark arched brows, "
            "plump soft naturally contoured satin lips with subtle natural moisture and tiny beauty mark beside upper-left lip corner, "
            "voluminous jet-black 3B/3C spiral corkscrew curls with fine interwoven electric-indigo highlights framing face, "
            "subtle asymmetrical half-smirk"
        )

        prefix_tag = f"phase3_multi_sweep/run_{eval_count:04d}_"
        wf["13"]["inputs"]["text_a"] = prefix_tag
        wf["5"]["inputs"]["master_seed"] = 0  # Standard frontal anchor pose

        # Submit to ComfyUI
        try:
            res = send_comfy_request("/prompt", method="POST", data={"prompt": wf, "client_id": "phase3_multi_evaluator"})
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
        while time.time() - wait_start < 180:
            try:
                hist = send_comfy_request(f"/history/{prompt_id}")
                if prompt_id in hist:
                    data = hist[prompt_id]
                    status_info = data.get("status", {})
                    if status_info.get("status_str") == "error":
                        err_msgs = [m[1].get("exception_message") for m in status_info.get("messages", []) if m[0] == "execution_error"]
                        print(f"  [-] ComfyUI Execution Error: {err_msgs if err_msgs else status_info}")
                        break
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
                    if rendered_file:
                        break
            except Exception:
                pass
            time.sleep(2.0)

        if not rendered_file or not rendered_file.is_file():
            print("  [-] Render timed out or output not found.")
            continue

        # Compute Multi-Anchor Parity
        parity = compute_multi_anchor_parity(rendered_file)
        c_score = parity["composite"]
        rating = "🌟 GOLDEN" if c_score >= 0.70 else ("✅ PASS" if c_score >= 0.64 else ("⚠️ DRIFT" if c_score >= 0.55 else "❌ FAIL"))
        print(f"  >> Multi-Anchor Parity: Composite={c_score:.4f} [Frontal={parity['frontal']:.4f}, 3/4={parity['p34']:.4f}, 90°={parity['p90']:.4f}] [{rating}]")

        record = dict(combo)
        record["signature"] = combo_sig
        record["run_index"] = eval_count
        record["prompt_id"] = prompt_id
        record["parity_composite"] = c_score
        record["parity_frontal"] = parity["frontal"]
        record["parity_p34"] = parity["p34"]
        record["parity_p90"] = parity["p90"]
        record["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        record["saved_filename"] = rendered_file.name

        # If high-parity composite candidate, stage for Master Phase 3
        if c_score >= 0.70:
            staged_name = f"multi_anchor_golden_score_{int(c_score*1000):04d}_run_{eval_count:04d}_{rendered_file.name}"
            staged_path = STAGING_DIR / staged_name
            shutil.copy2(rendered_file, staged_path)
            with open(staged_path.with_suffix(".json"), "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
            print(f"  🏆 [CURATED] Staged golden candidate to: {staged_name}")

        results.append(record)

        # Update ledger & leaderboard
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

