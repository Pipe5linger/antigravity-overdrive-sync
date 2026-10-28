"""
Cull & Curate: Entire 'before argon refactor' Root Directory
============================================================
Targets the parent directory C:\\Users\\boben\\Desktop\\before argon refactor:
1. Purges dataset_masks, tier_03_borderline_60_64, tier_04_drift_sub60.
2. Cleans up orphaned .txt caption files in scraps.
3. Evaluates all remaining candidate images (dataset_images, phase3_multi_sweep,
   tier_01, tier_02, miscellaneous, nested before argon refactor) using:
   - CV mask & corruption detection
   - InsightFace buffalo_l face parity (>= 0.65 threshold)
4. Migrates surviving High/Golden renders into D:\\AI\\Projects\\ComfyUI\\output\\Past Renders\\Tier_[1-4].
5. Removes empty directories.
"""

import os
import sys
import shutil
import time
from pathlib import Path
import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

TARGET_ROOT = Path(r"C:\Users\boben\Desktop\before argon refactor")
PAST_RENDERS = Path(r"D:\AI\Projects\ComfyUI\output\Past Renders")
ANCHOR_VAULT = Path(r"D:\AI\Projects\ComfyUI\output\reference_anchors")

TIER_FOLDERS = {
    "T1": PAST_RENDERS / "Tier_1",
    "T2": PAST_RENDERS / "Tier_2",
    "T3": PAST_RENDERS / "Tier_3",
    "T4": PAST_RENDERS / "Tier_4",
}

ANCHOR_WEIGHTS = {
    "anchor_frontal.png": 0.35,
    "anchor_low_angle.png": 0.25,
    "anchor_profile_left.png": 0.20,
    "anchor_profile_right.png": 0.20,
}

KNOWN_PURGE_SUBDIRS = [
    TARGET_ROOT / "dataset_masks",
    TARGET_ROOT / "tier_03_borderline_60_64",
    TARGET_ROOT / "tier_04_drift_sub60",
]

def log(msg: str):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")

def purge_known_subpar():
    log("=== Step 1: Purging Known Sub-Par Folders ===")
    total = 0
    for pdir in KNOWN_PURGE_SUBDIRS:
        if pdir.exists():
            count = len(list(pdir.rglob("*.*")))
            shutil.rmtree(pdir, ignore_errors=True)
            total += count
            log(f"  [-] Purged {pdir.name} ({count} files)")
    
    # Clean loose .txt files from scraps
    scraps_dir = TARGET_ROOT / "scraps"
    if scraps_dir.exists():
        txts = list(scraps_dir.rglob("*.txt"))
        for t in txts:
            t.unlink(missing_ok=True)
        log(f"  [-] Purged {len(txts)} loose .txt caption files from scraps")
        shutil.rmtree(scraps_dir, ignore_errors=True)

    log(f"✓ Step 1 Complete. Purged {total} sub-par files.")

def is_mask_image(file_path: Path, img_bgr=None) -> bool:
    name_lower = file_path.name.lower()
    if "_mask" in name_lower or "mask_" in name_lower or name_lower.endswith("-mask.png"):
        return True
    if img_bgr is None:
        img_bgr = cv2.imread(str(file_path))
    if img_bgr is None:
        return True
    b, g, r = cv2.split(img_bgr)
    diff1 = cv2.absdiff(b, g)
    diff2 = cv2.absdiff(g, r)
    is_grayscale = (cv2.countNonZero(diff1) == 0) and (cv2.countNonZero(diff2) == 0)
    if is_grayscale:
        gray = b
        total_pixels = gray.size
        black_white_pixels = np.count_nonzero((gray <= 10) | (gray >= 245))
        if black_white_pixels / total_pixels > 0.88:
            return True
    return False

def is_corrupted_or_mutated(file_path: Path, img_bgr=None) -> bool:
    if img_bgr is None:
        img_bgr = cv2.imread(str(file_path))
    if img_bgr is None or img_bgr.size == 0:
        return True
    if np.std(img_bgr) < 2.0:
        return True
    return False

def classify_tier(file_path: Path, face_bbox, img_shape) -> str:
    name = file_path.name.upper()
    if "_T1_" in name or "TIER_1" in name or "TIER1" in name or "PORTRAIT" in name or "HEADSHOT" in name:
        return "T1"
    if "_T2_" in name or "TIER_2" in name or "TIER2" in name or "BOUDOIR" in name or "ANATOMY" in name or "CURVES" in name:
        return "T2"
    if "_T3_" in name or "TIER_3" in name or "TIER3" in name or "COUTURE" in name or "FASHION" in name or "STREETWEAR" in name:
        return "T3"
    if "_T4_" in name or "TIER_4" in name or "TIER4" in name or "SPATIAL" in name or "ARCHITECTURAL" in name or "WIDE" in name:
        return "T4"
    if face_bbox is not None and img_shape is not None:
        x1, y1, x2, y2 = face_bbox
        face_area = max(0, x2 - x1) * max(0, y2 - y1)
        img_area = img_shape[0] * img_shape[1]
        ratio = face_area / max(1, img_area)
        if ratio >= 0.12:
            return "T1"
        elif ratio >= 0.04:
            return "T2"
        elif ratio >= 0.015:
            return "T3"
        else:
            return "T4"
    return "T2"

def move_with_dedup(src: Path, dst_dir: Path):
    dst = dst_dir / src.name
    if not dst.exists():
        shutil.move(src, dst)
        return dst
    stem, suffix = src.stem, src.suffix
    counter = 1
    while dst.exists():
        dst = dst_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    shutil.move(src, dst)
    return dst

def main():
    start_time = time.time()
    log("================================================================================")
    log("👑 CULL & CURATE: 'before argon refactor' MASTER SWEEP")
    log("================================================================================")

    # 1. Purge known sub-par
    purge_known_subpar()

    # 2. Init InsightFace
    log("=== Step 2: Initializing InsightFace & Loading Face Anchors ===")
    from insightface.app import FaceAnalysis
    face_app = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    face_app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.15)

    face_vault = ANCHOR_VAULT / "face"
    anchor_embs = {}
    for f in face_vault.glob("*.png"):
        img = cv2.imread(str(f))
        faces = face_app.get(img)
        best = max(faces, key=lambda fc: (fc.bbox[2] - fc.bbox[0]) * (fc.bbox[3] - fc.bbox[1]))
        anchor_embs[f.name] = best.normed_embedding
        log(f"  ✓ Anchor Loaded: {f.name}")

    # 3. Gather candidate images
    log("=== Step 3: Gathering Candidate Images ===")
    candidates = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        candidates.extend(list(TARGET_ROOT.rglob(ext)))

    total = len(candidates)
    log(f"✓ Found {total} candidate images across 'before argon refactor'.")

    stats = {
        "masks": 0,
        "corrupt": 0,
        "subpar": 0,
        "migrated": {"T1": 0, "T2": 0, "T3": 0, "T4": 0}
    }

    log("=== Step 4: Scanning, Evaluating & Migrating ===")
    for idx, fpath in enumerate(candidates, 1):
        if not fpath.exists():
            continue

        if idx % 100 == 0 or idx == total:
            elapsed = time.time() - start_time
            log(f"[{idx}/{total}] | Purged: Masks={stats['masks']}, SubPar={stats['subpar']} | Kept: T1={stats['migrated']['T1']}, T2={stats['migrated']['T2']}, T3={stats['migrated']['T3']}, T4={stats['migrated']['T4']} | Elapsed: {elapsed:.1f}s")

        try:
            img = cv2.imread(str(fpath))
            if is_corrupted_or_mutated(fpath, img):
                fpath.unlink(missing_ok=True)
                stats["corrupt"] += 1
                continue

            if is_mask_image(fpath, img):
                fpath.unlink(missing_ok=True)
                stats["masks"] += 1
                continue

            faces = face_app.get(img)
            if not faces:
                name_upper = fpath.name.upper()
                if "T4" in name_upper or "SPATIAL" in name_upper or "ARCHITECTURAL" in name_upper:
                    tier = "T4"
                    move_with_dedup(fpath, TIER_FOLDERS[tier])
                    stats["migrated"][tier] += 1
                    # Also move paired txt if exists
                    txt_path = fpath.with_suffix(".txt")
                    if txt_path.exists():
                        move_with_dedup(txt_path, TIER_FOLDERS[tier])
                    continue
                else:
                    fpath.unlink(missing_ok=True)
                    txt_path = fpath.with_suffix(".txt")
                    txt_path.unlink(missing_ok=True)
                    stats["subpar"] += 1
                    continue

            best_face = max(faces, key=lambda fc: (fc.bbox[2] - fc.bbox[0]) * (fc.bbox[3] - fc.bbox[1]))
            emb = best_face.normed_embedding

            parity = sum(ANCHOR_WEIGHTS[k] * float(np.dot(emb, anchor_embs[k])) for k in ANCHOR_WEIGHTS if k in anchor_embs)
            tier_tentative = classify_tier(fpath, best_face.bbox, img.shape)
            min_thresh = 0.60 if tier_tentative in ("T3", "T4") else 0.65

            if parity < min_thresh:
                fpath.unlink(missing_ok=True)
                txt_path = fpath.with_suffix(".txt")
                txt_path.unlink(missing_ok=True)
                stats["subpar"] += 1
                continue

            # Passed!
            move_with_dedup(fpath, TIER_FOLDERS[tier_tentative])
            stats["migrated"][tier_tentative] += 1
            txt_path = fpath.with_suffix(".txt")
            if txt_path.exists():
                move_with_dedup(txt_path, TIER_FOLDERS[tier_tentative])

        except Exception as e:
            try:
                fpath.unlink(missing_ok=True)
            except Exception:
                pass
            stats["corrupt"] += 1

    # Step 5: Clean up empty folders in TARGET_ROOT
    log("=== Step 5: Cleaning up empty folders in TARGET_ROOT ===")
    for root, dirs, files in os.walk(TARGET_ROOT, topdown=False):
        rpath = Path(root)
        if not any(rpath.iterdir()):
            try:
                rpath.rmdir()
                log(f"  Removed empty folder: {rpath.name}")
            except Exception:
                pass

    total_time = time.time() - start_time
    log("================================================================================")
    log("🎉 'before argon refactor' CULL COMPLETE!")
    log(f"  • Total Images Processed: {total}")
    log(f"  • Masks Purged          : {stats['masks']}")
    log(f"  • Sub-Par Purged        : {stats['subpar']}")
    log(f"  • Crowned & Migrated    : {sum(stats['migrated'].values())}")
    log(f"      - Tier 1 (Portraits): {stats['migrated']['T1']}")
    log(f"      - Tier 2 (Boudoir)  : {stats['migrated']['T2']}")
    log(f"      - Tier 3 (Couture)  : {stats['migrated']['T3']}")
    log(f"      - Tier 4 (Spatial)  : {stats['migrated']['T4']}")
    log(f"  • Elapsed Time          : {total_time:.1f}s")
    log("================================================================================")

if __name__ == "__main__":
    main()

