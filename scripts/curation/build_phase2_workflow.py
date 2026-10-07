"""
Build Phase 2 Vespera Mega-Sweep Workflow
=========================================
Takes D:\\AI\\Projects\\ComfyUI\\user\\default\\workflows\\My_fav_.json (the Phase 1 base),
modifies it with our validated Variation B settings:
  1. DoRA Power LoRA Loader:
     - vespera_zit_v5_master.safetensors @ 1.00
     - Z-Hip-Slider.safetensors @ 0.90 (cinched waist)
     - Z-Breast-Slider.safetensors @ -0.40 (natural firm high-set bust)
     - Z-Detail-Slider.safetensors @ 0.75 (skin micro-pores)
     - dark_dreamcore_style_ZIT_epoch_10.safetensors @ 0.35 (chiaroscuro shadow)
  2. RefactoredPromptWorkstation:
     - Full canonical Vespera persona tokens (cinched waist, almond hazel-green eyes, corkscrew curls)
  3. KSampler: 10 steps, CFG 1.0
  4. RefactoredPoseActionNode: Matrix Sweep (40 Rounds - 2000 Batch)
  5. SaveImage Prefix: phase2_mega_sweep/vespera_p2

Saves to:
  D:\\AI\\Projects\\ComfyUI\\user\\default\\workflows\\Phase2_Vespera_MegaSweep.json
"""

import json
import sys
from pathlib import Path

# Force UTF-8 stdout
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SOURCE_PATH = Path(r"D:\AI\Projects\ComfyUI\user\default\workflows\My_fav_.json")
TARGET_PATH = Path(r"D:\AI\Projects\ComfyUI\user\default\workflows\Phase2_Vespera_MegaSweep.json")

VESPERA_CANONICAL_PROMPT = (
    "vespera, alluring woman of French-Levantine and Mediterranean heritage with athletic narrow cinched waist, "
    "wide hips with full perfectly rounded gluteal contours, toned thighs, and natural firm high-set modest bust, "
    "unblemished luminous warm olive skin retaining photorealistic micro-pores, skin texture, and golden undertones with specular highlights on cheekbones and collarbones, "
    "sculpted facial structure with high cheekbones and soft-tapered button nose, captivating deep hazel-green almond-shaped eyes with soft-smudged smoky eyeliner, "
    "full soft satin lips with subtle natural moisture and a tiny beauty mark beside upper-left lip corner, voluminous jet-black 3B/3C spiral corkscrew curls with fine interwoven electric-indigo highlights framing face, "
    "subtle asymmetrical half-smirk"
)

def build_workflow():
    if not SOURCE_PATH.exists():
        print(f"[-] Source workflow missing: {SOURCE_PATH}")
        return

    with open(SOURCE_PATH, "r", encoding="utf-8") as f:
        wf = json.load(f)

    # Modify nodes
    for node in wf["nodes"]:
        nid = node["id"]
        ntype = node["type"]

        # 1. DoRA Power LoRA Loader (Node 3)
        if nid == 3 or ntype == "DoRA Power LoRA Loader":
            node["title"] = "⚡ DoRA Dynamic Power LoRA Loader (Phase 2 Candidate 2)"
            props = node.setdefault("properties", {})
            dora_props = props.setdefault("dora_power_lora", {})
            dora_props["rows"] = [
                {"enabled": True, "name": "vespera_zit_v5_master.safetensors", "strengthModel": 1.00, "strengthClip": 1.00},
                {"enabled": True, "name": "Z-Hip-Slider.safetensors", "strengthModel": 0.90, "strengthClip": 0.90},
                {"enabled": True, "name": "ZIB_SkinnyVoluptousSlider_v5.1.safetensors", "strengthModel": 0.60, "strengthClip": 0.60},
                {"enabled": True, "name": "Z-Detail-Slider.safetensors", "strengthModel": 0.75, "strengthClip": 0.75},
                {"enabled": True, "name": "dark_dreamcore_style_ZIT_epoch_10.safetensors", "strengthModel": 0.35, "strengthClip": 0.35}
            ]

        # 2. RefactoredPromptWorkstation (Node 88)
        elif nid == 88 or ntype == "RefactoredPromptWorkstation":
            node["title"] = "👑 Prompt Workstation (Vespera Sovereign Master Phase 2)"
            if "widgets_values" in node and len(node["widgets_values"]) > 1:
                node["widgets_values"][0] = 0 # seed
                node["widgets_values"][1] = VESPERA_CANONICAL_PROMPT # subject_core

        # 3. RefactoredPoseActionNode (Node 92)
        elif nid == 92 or ntype == "RefactoredPoseActionNode":
            if "widgets_values" in node:
                node["widgets_values"] = [0, "🔁 Matrix Sweep (40 Rounds - 2000 Batch)"]

        # 4. PrimitiveNode (Master Seed) (Node 90)
        elif nid == 90 or (ntype == "PrimitiveNode" and node.get("title") == "🎲 Refactored Master Seed"):
            node["widgets_values"] = [0, "increment"]

        # 5. Base KSampler (Node 11)
        elif nid == 11 or ntype == "KSampler":
            if "widgets_values" in node and len(node["widgets_values"]) >= 7:
                node["widgets_values"][0] = 0 # seed
                node["widgets_values"][2] = 10 # steps
                node["widgets_values"][3] = 1.0 # cfg

        # 6. FaceDetailer (Node 15)
        elif nid == 15 or ntype == "FaceDetailer":
            node["title"] = "👑 FaceDetailer (Vespera Sovereign Polish)"

        # 7. SaveImage (Node 18)
        elif nid == 18 or (ntype == "SaveImage" and "Standard" in node.get("title", "")):
            node["widgets_values"] = ["phase2_mega_sweep/vespera_p2"]

    with open(TARGET_PATH, "w", encoding="utf-8") as f:
        json.dump(wf, f, indent=2)

    print(f"[+] Successfully built Phase 2 Mega-Sweep Workflow:")
    print(f"    Destination: {TARGET_PATH}")
    print(f"    Size: {TARGET_PATH.stat().st_size:,} bytes")

if __name__ == "__main__":
    build_workflow()
