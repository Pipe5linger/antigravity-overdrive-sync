"""
Phase 2 Workflow Rewriter & Validator
====================================
Uses metadata from amy_R1_T1_01_Direct_Frontal_Portrait_s0_00005_.png as architectural blueprint,
combined with the Golden Likeness recipe from D:\\AI\\Projects\\ComfyUI\\output\\native_zit_sweep (Rank 2 Gold: 0.3543 Parity).

Key Harmonizations:
  1. Architecture: Full pipeline from amy_v5:
     - Lumina2 UNet + Qwen CLIP + VAE
     - DoRA Power LoRA Loader
     - Base KSampler (10 steps, euler / FlowMatchEulerDiscreteScheduler, CFG 1.0, 768x1024)
     - Forensic FaceDetailer (bbox/face_yolov8m.pt + SAM @ 768 guide, denoise 0.25)
     - HandDetailer (bbox/hand_yolov8s.pt + SAM @ 512 guide, denoise 0.25)
     - SaveImage + B&W Training Mask Extractor (BiRefNet)
  2. LoRA Stack (Gold Native ZIT Standard):
     - vespera_zit_v5_master.safetensors @ 1.05
     - Z-Hip-Slider.safetensors @ 1.00 (waist cinch & hip balance)
     - Z-Detail-Slider.safetensors @ 0.50 (micro-pores & skin realism)
     - light and shadow Portrait.safetensors @ 0.40 (cinematic chiaroscuro depth)
     - auto_strength_enabled: FALSE (prevents dynamic 3x weight distortion)
     - Breast Slider: 0.0 (permanently purged)
  3. Prompt Workstation & Facial Parity:
     - Pure Vespera identity anchor matching native_zit_sweep
     - Sanitized wardrobe enforcing covered attire for Tier 1 and Tier 3
"""

import os
import sys
import json
from pathlib import Path

# Force UTF-8 stdout
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
WORKFLOW_DEST = COMFY_DIR / "user" / "default" / "workflows" / "Phase2_Vespera_MegaSweep.json"
SCRATCH_GRAPH = PROJECT_ROOT / "scratch" / "phase2_prompt_graph.json"

AMY_PROMPT_SRC = PROJECT_ROOT / "scratch" / "amy_v5_metadata_prompt.json"
AMY_WORKFLOW_SRC = PROJECT_ROOT / "scratch" / "amy_v5_metadata_workflow.json"

VESPERA_CANONICAL_CORE = (
    "vespera, alluring woman of French-Levantine and Mediterranean heritage with athletic narrow cinched waist, "
    "wide hips with full perfectly rounded gluteal contours, toned thighs, and natural firm high-set modest bust, "
    "unblemished luminous warm olive skin retaining photorealistic micro-pores, skin texture, and golden undertones with specular highlights on cheekbones and collarbones, "
    "sculpted facial structure with high cheekbones and soft-tapered button nose, captivating deep hazel-green almond-shaped eyes with soft-smudged smoky eyeliner, "
    "full soft satin lips with subtle natural moisture and tiny beauty mark beside upper-left lip corner, "
    "voluminous jet-black 3B/3C spiral corkscrew curls with fine interwoven electric-indigo highlights framing face, subtle asymmetrical half-smirk"
)

def rewrite_workflow():
    if not AMY_PROMPT_SRC.exists() or not AMY_WORKFLOW_SRC.exists():
        print("[-] Amy v5 metadata source files missing.")
        return

    with open(AMY_PROMPT_SRC, "r", encoding="utf-8") as f:
        prompt_graph = json.load(f)

    with open(AMY_WORKFLOW_SRC, "r", encoding="utf-8") as f:
        ui_workflow = json.load(f)

    # 1. Update Prompt Graph Node 3 (DoRA Power LoRA Loader)
    n3 = prompt_graph["3"]["inputs"]
    n3["LORA_1"] = {"on": True, "lora": "vespera_zit_v5_master.safetensors", "strength": 1.05, "strengthTwo": 1.05}
    n3["LORA_2"] = {"on": True, "lora": "Z-Hip-Slider.safetensors", "strength": 1.00, "strengthTwo": 1.00}
    n3["LORA_3"] = {"on": True, "lora": "Z-Detail-Slider.safetensors", "strength": 0.50, "strengthTwo": 0.50}
    n3["LORA_4"] = {"on": True, "lora": "light and shadow Portrait.safetensors", "strength": 0.40, "strengthTwo": 0.40}
    n3["LORA_5"] = {"on": False, "lora": "None", "strength": 1.0, "strengthTwo": 1.0}
    n3["auto_strength_enabled"] = False
    n3["broadcast_auto_scale"] = False

    # 2. Update Latent Resolution (Node 10) to 768x1024
    if "10" in prompt_graph:
        prompt_graph["10"]["inputs"]["width"] = 768
        prompt_graph["10"]["inputs"]["height"] = 1024

    # 3. Update KSampler (Node 11)
    if "11" in prompt_graph:
        prompt_graph["11"]["inputs"]["steps"] = 10
        prompt_graph["11"]["inputs"]["cfg"] = 1.0
        prompt_graph["11"]["inputs"]["sampler_name"] = "euler"
        prompt_graph["11"]["inputs"]["scheduler"] = "FlowMatchEulerDiscreteScheduler"

    # 4. Update Node 88 (Prompt Workstation)
    if "88" in prompt_graph:
        prompt_graph["88"]["inputs"]["subject_core"] = VESPERA_CANONICAL_CORE
        prompt_graph["88"]["inputs"]["custom_negative"] = (
            "NSFW, nudity, exposed cleavage, lingerie, bare breasts, nipples, multiple people, duplicate person, "
            "deformed anatomy, poorly rendered, cartoon, 3d render, illustration, anime, low quality, blurry"
        )

    # 5. Save updated prompt graph
    SCRATCH_GRAPH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCRATCH_GRAPH, "w", encoding="utf-8") as f:
        json.dump(prompt_graph, f, indent=2)
    print(f"[+] Saved updated prompt graph to: {SCRATCH_GRAPH}")

    # 6. Update UI Workflow nodes to match
    for node in ui_workflow.get("nodes", []):
        nid = node.get("id")
        if nid == 10:  # Latent
            node["widgets_values"] = [768, 1024, 1]
        elif nid == 11:  # KSampler
            node["widgets_values"] = [0, "fixed", 10, 1.0, "euler", "FlowMatchEulerDiscreteScheduler", 1.0]
        elif nid == 88:  # Workstation
            wv = node.get("widgets_values", [])
            if len(wv) > 1:
                wv[1] = VESPERA_CANONICAL_CORE
                node["widgets_values"] = wv
        elif nid == 18:  # SaveImage
            node["widgets_values"] = ["phase2_mega_sweep/vespera_p2"]

    WORKFLOW_DEST.parent.mkdir(parents=True, exist_ok=True)
    with open(WORKFLOW_DEST, "w", encoding="utf-8") as f:
        json.dump(ui_workflow, f, indent=2)
    print(f"[+] Saved updated UI workflow to: {WORKFLOW_DEST}")

if __name__ == "__main__":
    rewrite_workflow()
