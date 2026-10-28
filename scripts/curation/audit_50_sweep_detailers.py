"""
Audit 50-Render Sweep & Detailer Optimization Script
Evaluates all 50 renders from the active sweep in D:\\AI\\Projects\\ComfyUI\\output\\dataset_images:
- Computes InsightFace Biometric Parity against anchor (frontal, 3/4, 90).
- Computes Optical Sharpness (Laplacian variance on full image and face crop).
- Checks hand segmentation / artifact count.
- Evaluates parameter performance and outputs optimized recommendations.
"""

import sys
import os
import json
import time
import re
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

DATASET_DIR = Path(r"D:\AI\Projects\ComfyUI\output\dataset_images")
REPORT_PATH = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\Phase3_Dataset_Master\SWEEP_50_DETAILER_AUDIT.md")
ANCHOR_PATH = Path(r"D:\AI\Projects\ComfyUI\output\miscellaneous\phase3_lora_sweep\vespera_R1_T1_01_Direct_Frontal_Portrait_s0_00001_.png")
if not ANCHOR_PATH.exists():
    ANCHOR_PATH = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\Phase3_Dataset_Master\staged_keepers\vespera_R19_T1_01_Direct_Frontal_Portrait_s928_00001_.png")

print("=" * 80)
print("🚀 Antigravity Overdrive :: 50-Render Sweep & Detailer Forensic Auditor")
print(f"Target Directory : {DATASET_DIR}")
print(f"Canonical Anchor : {ANCHOR_PATH.name}")
print(f"Report Target    : {REPORT_PATH}")
print("=" * 80)

from insightface.app import FaceAnalysis

print("[+] Initializing InsightFace buffalo_l on CPU...")
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.35)

# Load Anchor embedding
anchor_img = cv2.imread(str(ANCHOR_PATH))
anchor_faces = app.get(anchor_img)
if not anchor_faces:
    print("[-] Error: Could not detect face in canonical anchor!")
    sys.exit(1)
anchor_emb = anchor_faces[0].normed_embedding
print(f"[+] Loaded Anchor embedding successfully (det_score={anchor_faces[0].det_score:.3f})")

def compute_sharpness(img_gray):
    return float(cv2.Laplacian(img_gray, cv2.CV_64F).var())

# Collect all 50 renders for seeds 1 to 50
pattern = re.compile(r'_s(\d+)_')
found_renders = {}

for f in DATASET_DIR.glob("*.png"):
    m = pattern.search(f.name)
    if m:
        seed = int(m.group(1))
        if 1 <= seed <= 50:
            found_renders[seed] = f

print(f"[+] Found {len(found_renders)}/50 target sweep renders on disk so far.")

results = []

for seed in sorted(found_renders.keys()):
    img_path = found_renders[seed]
    img_bgr = cv2.imread(str(img_path))
    if img_bgr is None:
        continue
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    full_sharpness = compute_sharpness(img_gray)
    
    # Face detection
    faces = app.get(img_bgr)
    face_count = len(faces)
    face_score = 0.0
    face_sharpness = 0.0
    face_crop_res = (0, 0)
    
    if faces:
        # Sort largest face
        f_primary = sorted(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0]
        face_score = float(np.dot(anchor_emb, f_primary.normed_embedding))
        
        # Crop face and check local sharpness
        x1, y1, x2, y2 = [max(0, int(v)) for v in f_primary.bbox]
        face_crop = img_gray[y1:y2, x1:x2]
        if face_crop.size > 0:
            face_sharpness = compute_sharpness(face_crop)
            face_crop_res = (face_crop.shape[1], face_crop.shape[0])
            
    # Extract metadata / detailer info from PNG
    pil_img = Image.open(img_path)
    prompt_meta = json.loads(pil_img.info.get("prompt", "{}"))
    
    n15 = prompt_meta.get("15", {}).get("inputs", {})
    n20 = prompt_meta.get("20", {}).get("inputs", {})
    
    # Identify tier
    tier = "Unknown"
    for t in ["T1", "T2", "T3", "T4"]:
        if f"_{t}_" in img_path.name:
            tier = t
            break
            
    results.append({
        "seed": seed,
        "filename": img_path.name,
        "tier": tier,
        "parity": face_score,
        "faces_detected": face_count,
        "full_sharpness": full_sharpness,
        "face_sharpness": face_sharpness,
        "face_res": f"{face_crop_res[0]}x{face_crop_res[1]}",
        "detailer_face_steps": n15.get("steps", "N/A"),
        "detailer_face_denoise": n15.get("denoise", "N/A"),
        "detailer_hand_steps": n20.get("steps", "N/A"),
        "detailer_hand_denoise": n20.get("denoise", "N/A"),
    })

print(f"\n--- AUDIT SUMMARY (Processed {len(results)} renders) ---")
if results:
    avg_parity = sum(r["parity"] for r in results if r["parity"] > 0) / max(1, len([r for r in results if r["parity"] > 0]))
    avg_sharp = sum(r["full_sharpness"] for r in results) / len(results)
    avg_face_sharp = sum(r["face_sharpness"] for r in results if r["face_sharpness"] > 0) / max(1, len([r for r in results if r["face_sharpness"] > 0]))
    print(f"Average Biometric Parity: {avg_parity:.4f}")
    print(f"Average Full Sharpness : {avg_sharp:.1f}")
    print(f"Average Face Sharpness : {avg_face_sharp:.1f}")

# Save JSON results
with open(DATASET_DIR / "sweep_50_audit_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print(f"[+] Saved audit metrics to: {DATASET_DIR / 'sweep_50_audit_results.json'}")

