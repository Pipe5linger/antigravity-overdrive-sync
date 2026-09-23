import sys
import os
import json
from pathlib import Path
from PIL import Image

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
    except AttributeError:
        pass

RENDER_DIR = Path(r"D:\AI\Projects\ComfyUI\output\dataset_images")

def inspect_latest(render_dir=RENDER_DIR):
    if not render_dir.exists():
        print(f"[-] Directory does not exist: {render_dir}")
        return 0

    png_files = sorted(render_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not png_files:
        print("[*] No PNG renders found in dataset directory.")
        return 0

    latest = png_files[0]
    print(f"[*] Inspecting latest render: {latest.name} ({latest.stat().st_size // 1024} KB)")
    
    try:
        with Image.open(latest) as img:
            info = img.info
            meta_keys = list(info.keys())
            print(f"  Metadata chunks present: {meta_keys}")
            
            if "prompt" in info:
                prompt_data = json.loads(info["prompt"])
                lora_nodes = []
                for nid, nval in prompt_data.items():
                    ctype = nval.get("class_type", "")
                    if "lora" in ctype.lower():
                        inputs = nval.get("inputs", {})
                        lora_name = inputs.get("lora_name", "")
                        strength = inputs.get("strength_model", inputs.get("strength", 1.0))
                        lora_nodes.append(f"{lora_name} (str={strength})")
                if lora_nodes:
                    print(f"  Active LoRAs in frame: {', '.join(lora_nodes)}")
            
            print(f"[+] Render Resolution: {img.size[0]}x{img.size[1]} | Format: {img.format}")
    except Exception as e:
        print(f"[-] Failed extracting metadata: {e}")
    return 0

if __name__ == "__main__":
    sys.exit(inspect_latest())
