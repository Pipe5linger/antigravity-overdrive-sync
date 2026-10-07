"""
Phase 2 Vespera Mega-Sweep Orchestrator (2,000 Image Matrix Batch)
=================================================================
Automates the full 40-Round / 2000-Image dataset creation batch using Candidate 2:
  - Master LoRA: vespera_zit_v5_master.safetensors @ 1.00
  - Anatomy (Cinched Waist): Z-Hip-Slider.safetensors @ 0.90
  - Anatomy (Voluptuous Curves & Proportion): ZIB_SkinnyVoluptousSlider_v5.1.safetensors @ 0.60
  - Micro-Detail: Z-Detail-Slider.safetensors @ 0.75
  - Atmosphere: dark_dreamcore_style_ZIT_epoch_10.safetensors @ 0.35
  - Sampling: 10 steps, CFG 1.0, 768x1024
  - Pipeline: Lumina2 UNet + VAE Decode + FaceDetailer (YOLOv8 Face) + HandDetailer (YOLOv8 Hand)

De-biased & Sanitized:
  - Zero breast slider (zero nudity/cleavage bias across T1, T3, T4)
  - Zero navel references
  - Zero lip/eyeliner color bias

Fresh Dedicated Staging Directory:
  - D:\\AI\\Projects\\ComfyUI\\output\\phase2_mega_sweep_candidate2\\
  - D:\\AI\\Projects\\ZIT_LoRA_Trainer\\Phase2_MegaSweep_Candidate2\\dataset_images\\
  - D:\\AI\\Projects\\ZIT_LoRA_Trainer\\Phase2_MegaSweep_Candidate2\\dataset_captions\\
  - Progress: D:\\AI\\Projects\\ZIT_LoRA_Trainer\\Phase2_MegaSweep_Candidate2\\MEGA_SWEEP_PROGRESS.md
"""

import os
import sys
import json
import time
import shutil
import urllib.request
from pathlib import Path

# Add custom nodes to path for sweep engine
sys.path.append(r"D:\AI\Projects\ComfyUI\custom_nodes\ComfyUI-Vespera-ZIT")
try:
    from sweep_round_engine import get_round_attire, ROUND_MODULATIONS_40
    from pose_action_node_refactor import RefactoredPoseActionNode
    pose_node = RefactoredPoseActionNode()
except Exception as e:
    print(f"Warning: sweep_round_engine / pose_node import fallback: {e}")
    get_round_attire = None
    ROUND_MODULATIONS_40 = {}
    pose_node = None

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
SWEEP_DIR = ZIT_DIR / "Phase2_MegaSweep_Candidate2"
DATASET_IMAGES = SWEEP_DIR / "dataset_images"
DATASET_CAPTIONS = SWEEP_DIR / "dataset_captions"
STATE_FILE = SWEEP_DIR / "mega_sweep_state.json"
PROGRESS_REPORT = SWEEP_DIR / "MEGA_SWEEP_PROGRESS.md"
BASE_PROMPT_GRAPH_PATH = PROJECT_ROOT / "scratch" / "phase2_prompt_graph.json"

for d in [SWEEP_DIR, DATASET_IMAGES, DATASET_CAPTIONS]:
    d.mkdir(parents=True, exist_ok=True)

VESPERA_CANONICAL_PROMPT = (
    "vespera, alluring woman of French-Levantine and Mediterranean heritage with athletic narrow cinched waist, "
    "wide hips with full perfectly rounded gluteal contours, toned thighs, and natural firm high-set modest bust, "
    "unblemished luminous warm olive skin retaining photorealistic micro-pores, skin texture, and golden undertones with specular highlights on cheekbones and collarbones, "
    "sculpted facial structure with high cheekbones and soft-tapered button nose, captivating deep hazel-green almond-shaped eyes with soft-smudged smoky eyeliner, "
    "full soft satin lips with subtle natural moisture and a tiny beauty mark beside upper-left lip corner, voluminous jet-black 3B/3C spiral corkscrew curls with fine interwoven electric-indigo highlights framing face, "
    "subtle asymmetrical half-smirk"
)

def send_comfy_request(endpoint: str, method: str = "GET", data: dict = None, timeout: float = 20.0):
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

def load_or_init_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "total_target": 2000,
        "completed_seeds": [],
        "starting_seed": 1,
        "last_seed": None,
        "start_time": time.time(),
        "total_rendered": 0,
        "renders": []
    }

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def update_progress_markdown(state):
    completed = len(state["completed_seeds"])
    total = state["total_target"]
    pct = (completed / total) * 100.0 if total else 0.0
    elapsed_hr = (time.time() - state["start_time"]) / 3600.0
    rate_per_hr = completed / elapsed_hr if elapsed_hr > 0.05 else 0.0
    eta_hr = ((total - completed) / rate_per_hr) if rate_per_hr > 0 else 0.0

    lines = [
        "# Phase 2 2,000-Image Mega Sweep Batch Tracker (Candidate 2 Fresh Folder)",
        f"**Last Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Batch Progress:** **{completed} / {total}** ({pct:.1f}%)",
        f"**Elapsed Time:** {elapsed_hr:.2f} hours | **Render Rate:** {rate_per_hr:.1f} images/hour",
        f"**Estimated Time Remaining (ETA):** {eta_hr:.2f} hours",
        "",
        "### Recipe Specification (Candidate 2 Sovereign Gold Parity)",
        "- **Master Identity:** `vespera_zit_v5_master.safetensors` @ 1.05",
        "- **Waist Cinch:** `Z-Hip-Slider.safetensors` @ 1.00",
        "- **Micro-Detail:** `Z-Detail-Slider.safetensors` @ 0.50",
        "- **Atmosphere:** `light and shadow Portrait.safetensors` @ 0.40",
        "- **Anatomy Sliders:** Breast & Voluptuous Sliders purged to 0.0 (Zero Nudity Bias)",
        "- **Auto-Strength:** `auto_strength_enabled: False` (Native LoRA Norm Preservation)",
        "- **Pipeline:** Lumina2 UNet + VAE Decode + FaceDetailer (YOLOv8m + SAM @ 768) + HandDetailer (YOLOv8s @ 512)",
        "- **Parity Benchmark:** Verified 0.49 - 0.57 ArcFace (Gold likeness achieved)",
        "",
        f"### Fresh Dedicated Directories",
        f"- **ComfyUI Raw Outputs:** `{COMFY_OUTPUT_DIR / 'phase2_mega_sweep_candidate2'}`",
        f"- **Dataset Images:** `{DATASET_IMAGES}`",
        f"- **Dataset Captions:** `{DATASET_CAPTIONS}`",
        "",
        "| Seed | Round | Output Asset | Timestamp |",
        "|:---:|:---:|:---:|:---:|"
    ]

    for item in state["renders"][-30:]:
        lines.append(f"| `{item['seed']:04d}` | Round {item.get('round', 1)} | `{item['filename']}` | {item['timestamp']} |")

    with open(PROGRESS_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def run_mega_sweep(max_batch: int = 2000):
    if not BASE_PROMPT_GRAPH_PATH.exists():
        print(f"[-] Base prompt graph missing: {BASE_PROMPT_GRAPH_PATH}")
        return

    with open(BASE_PROMPT_GRAPH_PATH, "r", encoding="utf-8") as f:
        base_prompt = json.load(f)

    state = load_or_init_state()
    state["total_target"] = max_batch
    completed_set = set(state["completed_seeds"])

    print(f"\n=======================================================")
    print(f"[+] Starting Phase 2 Mega-Sweep (Fresh Candidate 2 Folder)")
    print(f"[+] Progress: {len(completed_set)} / {max_batch} already completed")
    print(f"[+] Output Directory: {COMFY_OUTPUT_DIR / 'phase2_mega_sweep_candidate2'}")
    print(f"[+] Dataset Vault: {DATASET_IMAGES}")
    print(f"[+] Progress Report: {PROGRESS_REPORT}")
    print(f"=======================================================\n")

    if state.get("completed_seeds"):
        start_seed = max(state["completed_seeds"]) + 1
    else:
        start_seed = state.get("starting_seed", 1)

    for seed in range(start_seed, max_batch + 1):
        if seed in completed_set:
            continue

        round_num = ((seed - 1) // 50) + 1
        pose_in_round = ((seed - 1) % 50) + 1
        print(f"\n--- [Image {seed} / {max_batch}] (Round {round_num:02d}/40 | Pose {pose_in_round:02d}/50 | Seed: {seed}) ---")

        # Clone prompt graph
        wf = json.loads(json.dumps(base_prompt))

        # Node 3: DoRA Power LoRA Loader (Gold Parity Standard: 0.49 - 0.57 ArcFace)
        dora = wf["3"]["inputs"]
        dora["LORA_1"] = {"on": True, "lora": "vespera_zit_v5_master.safetensors", "strength": 1.05, "strengthTwo": 1.05}
        dora["LORA_2"] = {"on": True, "lora": "Z-Hip-Slider.safetensors", "strength": 1.00, "strengthTwo": 1.00}
        dora["LORA_3"] = {"on": True, "lora": "Z-Detail-Slider.safetensors", "strength": 0.50, "strengthTwo": 0.50}
        dora["LORA_4"] = {"on": True, "lora": "light and shadow Portrait.safetensors", "strength": 0.40, "strengthTwo": 0.40}
        dora["LORA_5"] = {"on": False, "lora": "None", "strength": 1.0, "strengthTwo": 1.0}
        dora["auto_strength_enabled"] = False
        dora["broadcast_auto_scale"] = False

        # Seed injection across nodes
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

        # Phase 1 Filename Scheme: vespera_{active_tier_tag}_s{seed}_
        active_tag = f"R{round_num}_s{seed}"
        if pose_node:
            try:
                active_tag = pose_node.run(master_seed=seed, pose_action_mode="🔁 Matrix Sweep (40 Rounds - 2000 Batch)")[1]
            except Exception:
                pass

        if "18" in wf:
            wf["18"]["inputs"]["filename_prefix"] = f"phase2_mega_sweep_candidate2/vespera_{active_tag}_s{seed}_"

        # Submit prompt
        try:
            res = send_comfy_request("/prompt", method="POST", data={"prompt": wf, "client_id": "mega_sweep_orchestrator"})
            prompt_id = res.get("prompt_id")
            if not prompt_id:
                print(f"  [-] Submission failed: {res}")
                time.sleep(3)
                continue
        except Exception as e:
            print(f"  [-] ComfyUI unreachable: {e}")
            time.sleep(5)
            continue

        # Wait for render
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
                            candidate = COMFY_OUTPUT_DIR / subf / fname
                            if candidate.exists():
                                rendered_file = candidate
                                break
                    if rendered_file:
                        break
            except Exception:
                pass
            time.sleep(1.5)

        if not rendered_file:
            print(f"  [-] Render timed out for prompt {prompt_id}")
            continue

        # Copy to dedicated Phase 2 Dataset Vault
        dataset_dest = DATASET_IMAGES / rendered_file.name
        shutil.copy2(rendered_file, dataset_dest)

        # Generate synchronized caption file with dynamic round details
        tier_str = "T1" if pose_in_round <= 15 else ("T2" if pose_in_round <= 25 else ("T3" if pose_in_round <= 40 else "T4"))
        slot_idx = (pose_in_round - 1) if tier_str == "T1" else ((pose_in_round - 16) if tier_str == "T2" else ((pose_in_round - 26) if tier_str == "T3" else (pose_in_round - 41)))
        
        attire_desc = ""
        scene_desc = "cinematic Parisian atmosphere"
        light_desc = "directional cinematic lighting"
        if get_round_attire:
            try:
                attire_desc = get_round_attire(round_num, tier_str, slot_idx)
            except Exception:
                pass
        if ROUND_MODULATIONS_40 and round_num in ROUND_MODULATIONS_40:
            mod = ROUND_MODULATIONS_40[round_num]
            scene_desc = mod.get("env_tone", scene_desc)
            light_desc = mod.get("lighting", light_desc)

        attire_clause = f", {attire_desc}" if attire_desc else ""
        caption_text = (
            f"vespera, alluring woman of French-Levantine and Mediterranean heritage with athletic narrow cinched waist, "
            f"wide hips with full perfectly rounded gluteal contours, toned thighs, natural firm high-set modest bust, "
            f"unblemished luminous warm olive skin retaining photorealistic micro-pores and golden undertones, "
            f"sculpted facial structure with high cheekbones and soft-tapered button nose, captivating deep hazel-green almond-shaped eyes with soft-smudged smoky eyeliner, "
            f"full soft satin lips with subtle natural moisture and tiny beauty mark beside upper-left lip corner, "
            f"voluminous jet-black 3B/3C spiral corkscrew curls with fine interwoven electric-indigo highlights framing face, "
            f"subtle asymmetrical half-smirk{attire_clause}, set in {scene_desc}, {light_desc}, raw 35mm photograph"
        )
        caption_file = DATASET_CAPTIONS / f"{rendered_file.stem}.txt"
        with open(caption_file, "w", encoding="utf-8") as cf:
            cf.write(caption_text)

        print(f"  [+] Saved & Staged: {rendered_file.name}")

        state["completed_seeds"].append(seed)
        state["last_seed"] = seed
        state["total_rendered"] += 1
        state["renders"].append({
            "seed": seed,
            "round": round_num,
            "pose_index": pose_in_round,
            "filename": rendered_file.name,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        # Save checkpoint
        save_state(state)
        update_progress_markdown(state)

        # Periodic VRAM flush every 10 images
        if (seed + 1) % 10 == 0:
            free_comfy_vram()

    print("\n=======================================================")
    print(f"[+] Mega Sweep Batch Finished! Completed: {len(state['completed_seeds'])} / {max_batch}")
    print(f"[+] Images Directory: {DATASET_IMAGES}")
    print(f"[+] Captions Directory: {DATASET_CAPTIONS}")
    print("=======================================================")

if __name__ == "__main__":
    max_b = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    run_mega_sweep(max_batch=max_b)
