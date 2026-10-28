#!/usr/bin/env python3
"""
================================================================================
Antigravity Overdrive :: Parity Tiered Sorter Engine
================================================================================
Monitors / scans the root of D:\AI\Projects\ComfyUI\output, evaluates each image
against canonical reference anchors using InsightFace Best-Angle Max Match,
and copies (NEVER hardlinks) the image into tiered parity subfolders:

  - tier_01_golden_70_plus      (Score >= 0.70)
  - tier_02_high_65_69          (0.65 <= Score < 0.70)
  - tier_03_borderline_60_64    (0.60 <= Score < 0.65)
  - tier_04_drift_sub60         (Score < 0.60 or No Face)

Author: Vespera Caligo Neal & Bobby
Protocols Enforced:
  - Absolute Hardlink Prohibition (shutil.copy2 only)
  - Root-only scanning (ignores subdirectories)
  - Non-destructive processing (original remains in root)
  - Persistent JSON ledger tracking (.parity_sort_ledger.json)
  - Dual Mode (One-Shot CLI + Continuous Background Watcher)
================================================================================
"""

import sys
import os
import time
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Windows console encoding safeguard
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import numpy as np

# Suppress ONNX runtime / InsightFace noise
os.environ["ORT_LOGGING_LEVEL"] = "3"

# --- DEFAULT PATHS ---
COMFY_OUTPUT_ROOT = Path(r"D:\AI\Projects\ComfyUI\output")
ANCHOR_DIR = COMFY_OUTPUT_ROOT / "reference_anchors"
PARITY_SCANNED_DIR = COMFY_OUTPUT_ROOT / "Parity_Scanned"
LEDGER_FILE = COMFY_OUTPUT_ROOT / ".parity_sort_ledger.json"

TIER_FOLDERS = {
    "golden": COMFY_OUTPUT_ROOT / "tier_01_golden_70_plus",
    "high": COMFY_OUTPUT_ROOT / "tier_02_high_65_69",
    "borderline": COMFY_OUTPUT_ROOT / "tier_03_borderline_60_64",
    "drift": COMFY_OUTPUT_ROOT / "tier_04_drift_sub60",
}

# --- GLOBAL MODEL & ANCHOR CACHE ---
_FACE_APP = None
_ANCHOR_EMBEDDINGS = {}


def get_face_app():
    global _FACE_APP
    if _FACE_APP is None:
        from insightface.app import FaceAnalysis
        # Prioritize CUDA provider, fallback to CPU
        app = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
        _FACE_APP = app
    return _FACE_APP


def extract_primary_embedding(img_bgr):
    """Detects and extracts normed embedding from the primary face in image."""
    app = get_face_app()
    faces = app.get(img_bgr)
    if not faces:
        return None
    # Largest face by bounding box area
    primary = sorted(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]), reverse=True)[0]
    return primary.normed_embedding


def init_reference_anchors():
    """Loads and computes normed embeddings for the 3 canonical anchors."""
    global _ANCHOR_EMBEDDINGS
    if _ANCHOR_EMBEDDINGS:
        return _ANCHOR_EMBEDDINGS

    anchors = {
        "frontal": ANCHOR_DIR / "vespera_frontal_anchor.png",
        "profile_34": ANCHOR_DIR / "vespera_profile_34_anchor.png",
        "profile_90": ANCHOR_DIR / "vespera_profile_90_anchor.png",
    }

    print("[*] Initializing Canonical Parity Reference Anchors...")
    for key, path in anchors.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing canonical reference anchor: {path}")
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"Failed to load image from anchor path: {path}")
        emb = extract_primary_embedding(img)
        if emb is None:
            raise RuntimeError(f"InsightFace failed to extract face from anchor: {path.name}")
        _ANCHOR_EMBEDDINGS[key] = emb
        print(f"  ✓ Loaded Anchor [{key.upper()}]: {path.name}")

    return _ANCHOR_EMBEDDINGS


def compute_best_angle_parity(img_path: Path):
    """
    Evaluates candidate against Frontal, 3/4, and 90° anchors.
    Returns:
      {
         'best_score': float,
         'best_anchor': str,
         'sim_frontal': float,
         'sim_p34': float,
         'sim_p90': float,
         'detected': bool
      }
    """
    img = cv2.imread(str(img_path))
    if img is None:
        return {"best_score": 0.0, "best_anchor": "none", "sim_frontal": 0.0, "sim_p34": 0.0, "sim_p90": 0.0, "detected": False}

    emb = extract_primary_embedding(img)
    if emb is None:
        return {"best_score": 0.0, "best_anchor": "none", "sim_frontal": 0.0, "sim_p34": 0.0, "sim_p90": 0.0, "detected": False}

    sim_f = float(np.dot(emb, _ANCHOR_EMBEDDINGS["frontal"]))
    sim_34 = float(np.dot(emb, _ANCHOR_EMBEDDINGS["profile_34"]))
    sim_90 = float(np.dot(emb, _ANCHOR_EMBEDDINGS["profile_90"]))

    # Best-Angle Max Match
    scores = [("frontal", sim_f), ("profile_34", sim_34), ("profile_90", sim_90)]
    best_anchor, best_score = max(scores, key=lambda x: x[1])

    return {
        "best_score": best_score,
        "best_anchor": best_anchor,
        "sim_frontal": sim_f,
        "sim_p34": sim_34,
        "sim_p90": sim_90,
        "detected": True
    }


def classify_tier(score: float, detected: bool) -> tuple[str, Path]:
    """Determines tier name and target folder path based on score."""
    if not detected or score < 0.60:
        return "tier_04_drift_sub60", TIER_FOLDERS["drift"]
    elif score < 0.65:
        return "tier_03_borderline_60_64", TIER_FOLDERS["borderline"]
    elif score < 0.70:
        return "tier_02_high_65_69", TIER_FOLDERS["high"]
    else:
        return "tier_01_golden_70_plus", TIER_FOLDERS["golden"]


def load_ledger() -> dict:
    if LEDGER_FILE.is_file():
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_ledger(ledger: dict):
    tmp_path = LEDGER_FILE.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    tmp_path.replace(LEDGER_FILE)


def ensure_tier_directories():
    PARITY_SCANNED_DIR.mkdir(parents=True, exist_ok=True)
    for folder in TIER_FOLDERS.values():
        folder.mkdir(parents=True, exist_ok=True)


def safe_move_with_retry(src: Path, dst: Path, retries: int = 5, delay: float = 0.5) -> bool:
    """Attempts to move a file on Windows, retrying if locked by another process."""
    for attempt in range(retries):
        try:
            shutil.move(str(src), str(dst))
            return True
        except PermissionError:
            time.sleep(delay)
        except Exception:
            time.sleep(delay)
    try:
        shutil.move(str(src), str(dst))
        return True
    except Exception as e:
        print(f"  [-] Failed to move {src.name} -> {dst.name} after retries: {e}")
        return False


def is_file_ready(path: Path) -> bool:
    """Verifies that a newly created image has finished writing to disk and is not locked."""
    try:
        st = path.stat()
        if st.st_size == 0:
            return False
        # Try opening for read to ensure writer has released locks
        with open(path, "rb") as f:
            f.seek(0, 2)
        return True
    except (OSError, FileNotFoundError, PermissionError):
        return False


def touch_windows_file_times(filepath: Path, dt: datetime = None):
    """Sets CreationTime and LastWriteTime on Windows so Windows Explorer's Date column reflects current time."""
    if not sys.platform.startswith("win"):
        return
    import ctypes
    from ctypes import wintypes
    dt = dt or datetime.now()
    EPOCH_AS_FILETIME = 116444736000000000
    HUNDREDS_OF_NANOSECONDS = 10000000
    posix_ts = dt.timestamp()
    ft_val = int(posix_ts * HUNDREDS_OF_NANOSECONDS + EPOCH_AS_FILETIME)
    ft = wintypes.FILETIME(ft_val & 0xFFFFFFFF, ft_val >> 32)
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.SetFileTime.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

    h_file = kernel32.CreateFileW(
        str(filepath), 0x40000000, 0x00000001 | 0x00000002, None, 3, 0x80, None
    )
    if h_file != -1:
        kernel32.SetFileTime(h_file, ctypes.byref(ft), None, ctypes.byref(ft))
        kernel32.CloseHandle(h_file)


def process_candidate_image(img_path: Path, ledger: dict) -> dict | None:
    """Evaluates one image, copies to tier, and moves original to Parity_Scanned."""
    fname = img_path.name
    try:
        st = img_path.stat()
    except (OSError, FileNotFoundError):
        return None

    # Check if already processed with identical mtime and size
    if fname in ledger:
        rec = ledger[fname]
        if rec.get("file_size") == st.st_size and rec.get("mtime") == st.st_mtime:
            # File was already evaluated in ledger; move original from root to Parity_Scanned
            archive_path = PARITY_SCANNED_DIR / fname
            if img_path.is_file():
                if safe_move_with_retry(img_path, archive_path):
                    touch_windows_file_times(archive_path)
                    print(f"  [>] Already in ledger: moved original {fname} -> Parity_Scanned")
            return None

    # Parity Evaluation
    res = compute_best_angle_parity(img_path)
    score = res["best_score"]
    tier_name, tier_dir = classify_tier(score, res["detected"])

    # 1. Physical copy into destination tier (NEVER HARDLINK)
    dest_path = tier_dir / fname
    shutil.copy2(img_path, dest_path)
    touch_windows_file_times(dest_path)

    # 2. Move original render from output root into Parity_Scanned subfolder
    archive_path = PARITY_SCANNED_DIR / fname
    if not safe_move_with_retry(img_path, archive_path):
        return None
    touch_windows_file_times(archive_path)

    record = {
        "filename": fname,
        "file_size": st.st_size,
        "mtime": st.st_mtime,
        "parity_score": round(score, 4),
        "best_anchor": res["best_anchor"],
        "sim_frontal": round(res["sim_frontal"], 4),
        "sim_p34": round(res["sim_p34"], 4),
        "sim_p90": round(res["sim_p90"], 4),
        "detected": res["detected"],
        "tier": tier_name,
        "tier_copy_path": str(dest_path),
        "parity_scanned_path": str(archive_path),
        "timestamp": datetime.now().isoformat()
    }
    ledger[fname] = record

    rating = "🌟 GOLDEN" if score >= 0.70 else ("✅ HIGH" if score >= 0.65 else ("⚠️ BORDERLINE" if score >= 0.60 else "❌ DRIFT"))
    print(f"  [+] {fname} -> {tier_name} [Score: {score:.4f} via {res['best_anchor']}] [{rating}] | Archived -> Parity_Scanned")
    return record


def scan_and_sort(output_root: Path = COMFY_OUTPUT_ROOT, verbose: bool = True):
    """Performs one scan of the output root directory."""
    ensure_tier_directories()
    ledger = load_ledger()

    # Find candidate image files strictly in ROOT (ignore subdirectories)
    valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
    candidates = [
        f for f in output_root.iterdir()
        if f.is_file() and f.suffix.lower() in valid_exts and not f.name.startswith(".")
    ]

    if verbose:
        print(f"[*] Scanning output root: {output_root}")
        print(f"[*] Total image files found in root: {len(candidates)}")
        print(f"[*] Previously processed in ledger: {len(ledger)}")

    newly_processed = 0
    tier_counts = {"tier_01_golden_70_plus": 0, "tier_02_high_65_69": 0, "tier_03_borderline_60_64": 0, "tier_04_drift_sub60": 0}

    for cand in sorted(candidates, key=lambda x: x.stat().st_mtime):
        try:
            if not is_file_ready(cand):
                continue
            rec = process_candidate_image(cand, ledger)
            if rec is not None:
                newly_processed += 1
                tier_counts[rec["tier"]] = tier_counts.get(rec["tier"], 0) + 1
        except Exception as cand_err:
            print(f"  [-] Error processing candidate {cand.name}: {cand_err}")

    if newly_processed > 0:
        save_ledger(ledger)
        print(f"\n[✓] Run Completed: {newly_processed} new images classified and copied.")
        print(f"    - 🌟 Golden 70+     : {tier_counts['tier_01_golden_70_plus']}")
        print(f"    - ✅ High 65-69      : {tier_counts['tier_02_high_65_69']}")
        print(f"    - ⚠️ Borderline 60-64: {tier_counts['tier_03_borderline_60_64']}")
        print(f"    - ❌ Drift Sub-60    : {tier_counts['tier_04_drift_sub60']}")
    elif verbose:
        print("[*] Output root is fully synchronized with ledger. No new images to sort.")

    return newly_processed


def watch_mode(output_root: Path = COMFY_OUTPUT_ROOT, interval: float = 5.0):
    """Continuous watcher polling output root for newly dropped images."""
    print("=" * 80)
    print("👁️ Antigravity Overdrive :: Parity Tier Sorter [CONTINUOUS WATCHER MODE]")
    print(f"Watching Root Directory : {output_root}")
    print(f"Polling Interval        : {interval} seconds")
    print(f"Hardlink Taboo          : Active (All operations use shutil.copy2)")
    print("Press Ctrl+C to halt watcher.")
    print("=" * 80)

    # Initial scan
    try:
        scan_and_sort(output_root, verbose=True)
    except Exception as e:
        print(f"[-] Initial scan warning: {e}")

    try:
        while True:
            time.sleep(interval)
            try:
                scan_and_sort(output_root, verbose=False)
            except Exception as loop_e:
                print(f"[-] Watcher cycle warning: {loop_e}")
    except KeyboardInterrupt:
        print("\n[*] Watcher terminated gracefully by user.")


def main():
    parser = argparse.ArgumentParser(description="Parity Tiered Sorter Engine")
    parser.add_argument("--watch", action="store_true", help="Run continuously in background watcher mode")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds for watch mode")
    parser.add_argument("--root", type=str, default=str(COMFY_OUTPUT_ROOT), help="Custom output root folder to scan")
    args = parser.parse_args()

    init_reference_anchors()

    root_path = Path(args.root)
    if not root_path.is_dir():
        print(f"[-] Target output root does not exist: {root_path}")
        sys.exit(1)

    if args.watch:
        watch_mode(root_path, interval=args.interval)
    else:
        scan_and_sort(root_path, verbose=True)


if __name__ == "__main__":
    main()

