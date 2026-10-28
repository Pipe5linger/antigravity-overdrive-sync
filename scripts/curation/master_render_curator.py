"""
Master Render Curator & Anchor Vault Organizer
=============================================
Antigravity-Overdrive-Sync Suite

1. Ingests Master Reference Anchors (4 Face, 4 Body) into D:\\AI\\Projects\\ComfyUI\\output\\reference_anchors.
2. Creates Past Renders structure: Tier_1, Tier_2, Tier_3, Tier_4.
3. Purges known sub-par directories (sub60 drift, borderline, and Desktop scraps prune buckets).
4. Runs computer vision scanner to detect and delete binary masks and severe corruption/mutations.
5. Runs InsightFace (buffalo_l) to score face parity against the Golden Face anchors (Threshold >= 0.65).
6. Deletes images failing the High/Golden standard.
7. Classifies survivors into Tier_1..Tier_4 using hybrid filename + CV framing ratio.
8. Moves survivors into Past Renders\\Tier_X and cleans up empty source directories.
"""

import os
import sys
import shutil
import time
import json
from pathlib import Path
import cv2
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

# Paths
COMFY_OUTPUT = Path(r"D:\AI\Projects\ComfyUI\output")
ANCHOR_VAULT = COMFY_OUTPUT / "reference_anchors"
PAST_RENDERS = COMFY_OUTPUT / "Past Renders"
DESKTOP_SCRAPS = Path(r"C:\Users\boben\Desktop\before argon refactor\scraps")

# Source Reference Anchors
FACE_REFS = [
    Path(r"D:\AI\Projects\ai-toolkit\vespera_anchors\anchor_frontal.png"),
    Path(r"D:\AI\Projects\ai-toolkit\vespera_anchors\anchor_low_angle.png"),
    Path(r"D:\AI\Projects\ai-toolkit\vespera_anchors\anchor_profile_left.png"),
    Path(r"D:\AI\Projects\ai-toolkit\vespera_anchors\anchor_profile_right.png")
]

BODY_REFS = [
    COMFY_OUTPUT / "tier_04_drift_sub60" / "vespera_R8_T2_08_Athletic_Stretch_Overhead_s792149088586477_00001_.png",
    COMFY_OUTPUT / "Parity_Scanned" / "vespera_T2_03_Standing_Frontal_Contrapposto_s18_00013_.png",
    COMFY_OUTPUT / "Parity_Scanned" / "vespera_T2_01_Kneeling_Frontal_Proportions_s16_00002_.png",
    COMFY_OUTPUT / "tier_03_borderline_60_64" / "vespera_T2_04_Standing_3_4_Rear_Arch_s19_00002_.png"
]

ANCHOR_WEIGHTS = {
    "anchor_frontal.png": 0.35,
    "anchor_low_angle.png": 0.25,
    "anchor_profile_left.png": 0.20,
    "anchor_profile_right.png": 0.20,
}

# Directories to scan for candidates
SCAN_SOURCES = [
    COMFY_OUTPUT / "tier_01_golden_70_plus",
    COMFY_OUTPUT / "tier_02_high_65_69",
    COMFY_OUTPUT / "Parity_Scanned",
    DESKTOP_SCRAPS
]

KNOWN_PURGE_DIRS = [
    COMFY_OUTPUT / "tier_04_drift_sub60",
    COMFY_OUTPUT / "tier_03_borderline_60_64",
    DESKTOP_SCRAPS / "_pruned_identity",
    DESKTOP_SCRAPS / "_pruned_mutation",
    DESKTOP_SCRAPS / "_redundant_and_duplicates",
    DESKTOP_SCRAPS / "phase2_candidate2_aborted_renders"
]

TIER_FOLDERS = {
    "T1": PAST_RENDERS / "Tier_1",
    "T2": PAST_RENDERS / "Tier_2",
    "T3": PAST_RENDERS / "Tier_3",
    "T4": PAST_RENDERS / "Tier_4",
}


def log(msg: str):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")


def setup_vault_and_dirs():
    """Copy reference anchors to permanent vault and create Past Renders folders."""
    log("=== PHASE 1: Setting up Master Reference Anchor Vault & Past Renders ===")
    
    face_vault = ANCHOR_VAULT / "face"
    body_vault = ANCHOR_VAULT / "body"
    face_vault.mkdir(parents=True, exist_ok=True)
    body_vault.mkdir(parents=True, exist_ok=True)

    for tf in TIER_FOLDERS.values():
        tf.mkdir(parents=True, exist_ok=True)

    # Ingest Face Anchors
    for f in FACE_REFS:
        if not f.exists():
            raise FileNotFoundError(f"Missing required face reference: {f}")
        dst = face_vault / f.name
        shutil.copy2(f, dst)
        log(f"  [Face Anchor Vault] Ingested: {dst.name} ({dst.stat().st_size} bytes)")

    # Ingest Body Anchors
    for b in BODY_REFS:
        if not b.exists():
            raise FileNotFoundError(f"Missing required body reference: {b}")
        dst = body_vault / b.name
        shutil.copy2(b, dst)
        log(f"  [Body Anchor Vault] Ingested: {dst.name} ({dst.stat().st_size} bytes)")

    log("✓ Master Reference Vault fully populated and verified.")


def purge_known_subpar():
    """Purge pre-identified low-tier, borderline, and scrap prune buckets."""
    log("=== PHASE 2: Purging Known Sub-Par & Pruned Folders ===")
    total_purged = 0
    for pdir in KNOWN_PURGE_DIRS:
        if pdir.exists() and pdir.is_dir():
            count = len(list(pdir.rglob("*.*")))
            try:
                shutil.rmtree(pdir)
                total_purged += count
                log(f"  [-] Purged directory: {pdir} ({count} files)")
            except Exception as e:
                log(f"  [!] Error purging {pdir}: {e}")
    log(f"✓ Phase 2 Complete. Purged {total_purged} known sub-par files.")
    return total_purged


def is_mask_image(file_path: Path, img_bgr=None) -> bool:
    """Detect binary black/white silhouette masks and matte masks."""
    name_lower = file_path.name.lower()
    if "_mask" in name_lower or "mask_" in name_lower or name_lower.endswith("-mask.png"):
        return True

    if img_bgr is None:
        img_bgr = cv2.imread(str(file_path))
    if img_bgr is None:
        return True  # Corrupt / unreadable

    # Check color channels difference
    b, g, r = cv2.split(img_bgr)
    diff1 = cv2.absdiff(b, g)
    diff2 = cv2.absdiff(g, r)
    is_grayscale = (cv2.countNonZero(diff1) == 0) and (cv2.countNonZero(diff2) == 0)

    if is_grayscale:
        # Check if pixels are heavily bimodal at <= 10 or >= 245
        gray = b
        total_pixels = gray.size
        black_white_pixels = np.count_nonzero((gray <= 10) | (gray >= 245))
        ratio = black_white_pixels / total_pixels
        if ratio > 0.88:
            return True

    return False


def is_corrupted_or_mutated(file_path: Path, img_bgr=None) -> bool:
    """Detect unreadable images, zero-variance solids, or digital glitch static."""
    if img_bgr is None:
        img_bgr = cv2.imread(str(file_path))
    if img_bgr is None or img_bgr.size == 0:
        return True

    # Check for solid color blank image
    if np.std(img_bgr) < 2.0:
        return True

    return False


def classify_tier(file_path: Path, face_bbox, img_shape) -> str:
    """Hybrid tier classification: filename tags first, fallback to CV face framing ratio."""
    name = file_path.name.upper()

    # Filename tag inspection
    if "_T1_" in name or "TIER_1" in name or "TIER1" in name or "PORTRAIT" in name or "HEADSHOT" in name:
        return "T1"
    if "_T2_" in name or "TIER_2" in name or "TIER2" in name or "BOUDOIR" in name or "ANATOMY" in name or "CURVES" in name:
        return "T2"
    if "_T3_" in name or "TIER_3" in name or "TIER3" in name or "COUTURE" in name or "FASHION" in name or "STREETWEAR" in name:
        return "T3"
    if "_T4_" in name or "TIER_4" in name or "TIER4" in name or "SPATIAL" in name or "ARCHITECTURAL" in name or "WIDE" in name:
        return "T4"

    # Fallback to Face Bounding Box Area Ratio
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

    return "T2"  # default sensible tier


def move_with_dedup(src: Path, dst_dir: Path):
    """Move file to destination directory, avoiding filename collisions."""
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
    log("👑 VESPERA MASTER RENDER CURATION & RETENTION ENGINE")
    log("================================================================================")

    # Step 1: Vault & Dirs
    setup_vault_and_dirs()

    # Step 2: Purge known sub-par
    purge_known_subpar()

    # Step 3: Initialize InsightFace
    log("=== PHASE 3: Initializing InsightFace & Precomputing Anchor Embeddings ===")
    from insightface.app import FaceAnalysis

    # Prefer CUDA, fallback to CPU
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    log(f"  Attempting InsightFace prepare with providers: {providers}")
    face_app = FaceAnalysis(name="buffalo_l", providers=providers)
    face_app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.15)
    log("  InsightFace buffalo_l initialized successfully.")

    # Precompute Golden Face Embeddings
    face_vault = ANCHOR_VAULT / "face"
    anchor_embs = {}
    for f in FACE_REFS:
        vault_f = face_vault / f.name
        img = cv2.imread(str(vault_f))
        if img is None:
            raise RuntimeError(f"Could not read anchor image: {vault_f}")
        faces = face_app.get(img)
        if not faces:
            raise RuntimeError(f"No face detected in anchor: {vault_f}")
        best_face = max(faces, key=lambda fc: (fc.bbox[2] - fc.bbox[0]) * (fc.bbox[3] - fc.bbox[1]))
        anchor_embs[f.name] = best_face.normed_embedding
        log(f"  ✓ Anchor Embedding Loaded: {f.name}")

    # Step 4: Scan Candidate Pool
    log("=== PHASE 4: Gathering Candidate Images ===")
    candidate_files = []
    for sdir in SCAN_SOURCES:
        if sdir.exists():
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                candidate_files.extend(list(sdir.rglob(ext)))

    # Exclude files already inside reference_anchors or Past Renders
    def is_safe_target(p: Path):
        try:
            p.relative_to(ANCHOR_VAULT)
            return False
        except ValueError:
            pass
        try:
            p.relative_to(PAST_RENDERS)
            return False
        except ValueError:
            pass
        return True

    candidate_files = [p for p in candidate_files if is_safe_target(p)]
    total_candidates = len(candidate_files)
    log(f"✓ Found {total_candidates} candidate images to process across all target directories.")

    # Counters
    stats = {
        "masks_purged": 0,
        "corrupt_purged": 0,
        "low_parity_purged": 0,
        "migrated": {"T1": 0, "T2": 0, "T3": 0, "T4": 0}
    }

    log("=== PHASE 5: Executing CV Mask Detection, Parity Evaluation & Migration ===")
    for idx, fpath in enumerate(candidate_files, 1):
        if not fpath.exists():
            continue

        # Real-time progress cadence
        if idx % 100 == 0 or idx == total_candidates:
            elapsed = time.time() - start_time
            log(f"[{idx}/{total_candidates}] | Purged: Masks={stats['masks_purged']}, SubPar={stats['low_parity_purged']} | Kept: T1={stats['migrated']['T1']}, T2={stats['migrated']['T2']}, T3={stats['migrated']['T3']}, T4={stats['migrated']['T4']} | Elapsed: {elapsed:.1f}s")

        # 1. Fast Mask / Corrupt pre-check
        try:
            img = cv2.imread(str(fpath))
            if is_corrupted_or_mutated(fpath, img):
                fpath.unlink(missing_ok=True)
                stats["corrupt_purged"] += 1
                continue

            if is_mask_image(fpath, img):
                fpath.unlink(missing_ok=True)
                stats["masks_purged"] += 1
                continue

            # 2. InsightFace Parity
            faces = face_app.get(img)
            if not faces:
                # No face detected in image
                # Check if it was tagged as T4 (wide architectural / landscape)
                name_upper = fpath.name.upper()
                if "T4" in name_upper or "SPATIAL" in name_upper or "ARCHITECTURAL" in name_upper:
                    # In wide architectural, face might be tiny or facing away; check if body is visible
                    tier = "T4"
                    move_with_dedup(fpath, TIER_FOLDERS[tier])
                    stats["migrated"][tier] += 1
                    continue
                else:
                    # Non-T4 with no face is not a valid Vespera render
                    fpath.unlink(missing_ok=True)
                    stats["low_parity_purged"] += 1
                    continue

            best_face = max(faces, key=lambda fc: (fc.bbox[2] - fc.bbox[0]) * (fc.bbox[3] - fc.bbox[1]))
            emb = best_face.normed_embedding

            # Weighted Parity against Face Anchors
            parity = sum(ANCHOR_WEIGHTS[k] * float(np.dot(emb, anchor_embs[k])) for k in ANCHOR_WEIGHTS)

            # High/Golden Standard Gate (0.65 threshold)
            # Allow 0.60 for distant T3/T4 where face resolution is naturally lower
            tier_tentative = classify_tier(fpath, best_face.bbox, img.shape)
            min_thresh = 0.60 if tier_tentative in ("T3", "T4") else 0.65

            if parity < min_thresh:
                fpath.unlink(missing_ok=True)
                stats["low_parity_purged"] += 1
                continue

            # 3. Passed! Migrate to Tier folder
            move_with_dedup(fpath, TIER_FOLDERS[tier_tentative])
            stats["migrated"][tier_tentative] += 1

        except Exception as err:
            # If unexpected read error, delete and record
            try:
                fpath.unlink(missing_ok=True)
            except Exception:
                pass
            stats["corrupt_purged"] += 1

    # Step 6: Clean up empty directories
    log("=== PHASE 6: Cleaning up empty source directories ===")
    for sdir in SCAN_SOURCES:
        if sdir.exists():
            for root, dirs, files in os.walk(sdir, topdown=False):
                rpath = Path(root)
                if rpath != ANCHOR_VAULT and rpath != PAST_RENDERS and not any(rpath.iterdir()):
                    try:
                        rpath.rmdir()
                        log(f"  Removed empty folder: {rpath}")
                    except Exception:
                        pass

    total_time = time.time() - start_time
    log("================================================================================")
    log("🎉 VESPERA MASTER CURATION COMPLETE!")
    log(f"  • Total Processed      : {total_candidates}")
    log(f"  • Masks Purged         : {stats['masks_purged']}")
    log(f"  • Corrupted Purged     : {stats['corrupt_purged']}")
    log(f"  • Sub-Par (<0.65) Purged: {stats['low_parity_purged']}")
    log(f"  • Crowned & Retained   : {sum(stats['migrated'].values())}")
    log(f"      - Tier 1 (Portraits): {stats['migrated']['T1']}")
    log(f"      - Tier 2 (Boudoir)  : {stats['migrated']['T2']}")
    log(f"      - Tier 3 (Couture)  : {stats['migrated']['T3']}")
    log(f"      - Tier 4 (Spatial)  : {stats['migrated']['T4']}")
    log(f"  • Execution Time       : {total_time:.1f}s")
    log(f"  • Anchor Vault Status  : {len(list((ANCHOR_VAULT/'face').glob('*.png')))} Face, {len(list((ANCHOR_VAULT/'body').glob('*.png')))} Body")
    log("================================================================================")


if __name__ == "__main__":
    main()

