import os
import sys
import glob
from pathlib import Path
from PIL import Image

DATASET_DIR = Path(r"D:\AI\Projects\ComfyUI\output\dataset_images")
QUARANTINE_DIR = DATASET_DIR / "_quarantine"

def audit_and_organize_harvest(target_dir=DATASET_DIR):
    if not target_dir.exists():
        print(f"[-] Directory does not exist: {target_dir}")
        return 0

    image_files = list(target_dir.glob("*.png")) + list(target_dir.glob("*.jpg"))
    print(f"[*] Found {len(image_files)} image files in {target_dir}")
    
    valid_count = 0
    anomalies = 0

    for img_path in image_files:
        try:
            with Image.open(img_path) as img:
                w, h = img.size
                if w < 512 or h < 512:
                    print(f"[!] Warning: Low resolution detected on {img_path.name}: {w}x{h}")
                    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
                    img.close()
                    dest = QUARANTINE_DIR / img_path.name
                    img_path.replace(dest)
                    anomalies += 1
                    continue
                valid_count += 1
        except Exception as e:
            print(f"[-] Corrupted render {img_path.name}: {e}")
            QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
            dest = QUARANTINE_DIR / img_path.name
            try:
                img_path.replace(dest)
            except Exception:
                pass
            anomalies += 1

    print(f"[+] Harvest Audit Complete: {valid_count} validated, {anomalies} quarantined.")
    return 0

if __name__ == "__main__":
    sys.exit(audit_and_organize_harvest())
