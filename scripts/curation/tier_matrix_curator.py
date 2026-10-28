"""
tier_matrix_curator.py
======================
Automated Tier-Matrix Classification & Dataset Curation Tool.

Purpose:
--------
Classifies raw photographic pools into the 4 canonical tiers of the ZIT (Z-Image-Turbo)
Pose & Action Engine matrix:
  - Tier 1: Identity Anchors (15 slots) -> Macro & Close-Up Face Portraits
  - Tier 2: Raw Anatomy & Form (10 slots) -> Mid-shots & Torso with Natural Proportions
  - Tier 3: Wardrobe Agnosticism (15 slots) -> Diverse Outfits, Fabrics, and Styles
  - Tier 4: 3D Spatial Awareness (10 slots) -> Full-Length Head-to-Toe, Motion & Perspective

Usage:
------
python tier_matrix_curator.py --input_dir <path> --output_dir <path>
"""

import os
import sys
import json
import time
import shutil
import argparse
import cv2
import numpy as np
from PIL import Image

# Ensure standard UTF-8 stream handling on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class TierMatrixCurator:
    def __init__(self, input_dir, output_dir, quotas=None, dry_run=False):
        self.input_dir = os.path.abspath(input_dir)
        self.output_dir = os.path.abspath(output_dir)
        self.dry_run = dry_run
        
        self.quotas = quotas or {
            "tier1": 15,
            "tier2": 10,
            "tier3": 15,
            "tier4": 10
        }
        
        # Load OpenCV Haar Cascades
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
        self.fullbody_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_fullbody.xml")

    def analyze_image(self, fpath):
        """Analyzes a single image file for framing, facial metrics, skin ratio, and sharpness."""
        img = cv2.imread(fpath)
        if img is None:
            return None

        h, w = img.shape[:2]
        
        # Normalize processing scale to max 1024px for consistent speed & metric evaluation
        scale = 1024.0 / max(h, w)
        gn = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1.0 else img
        gray = cv2.cvtColor(gn, cv2.COLOR_BGR2GRAY)
        gh, gw = gray.shape

        global_lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 1. Face Detection
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
        is_profile = False
        if len(faces) == 0:
            faces = self.profile_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
            is_profile = True

        face_detected = len(faces) > 0
        face_ratio = 0.0
        face_sharpness = 0.0
        eyes_detected = 0
        skin_pct = 0.0
        fw_orig, fh_orig = 0, 0

        if face_detected:
            fx, fy, fw, fh = max(faces, key=lambda b: b[2] * b[3])
            face_ratio = float(fh) / float(gh)
            
            # Map back to original resolution dimensions
            inv_scale = 1.0 / scale if scale < 1.0 else 1.0
            fw_orig = int(fw * inv_scale)
            fh_orig = int(fh * inv_scale)

            face_roi = gray[fy:fy+fh, fx:fx+fw]
            if face_roi.size > 0:
                face_sharpness = float(cv2.Laplacian(face_roi, cv2.CV_64F).var())
                if not is_profile:
                    eyes = self.eye_cascade.detectMultiScale(face_roi, 1.1, 2)
                    eyes_detected = len(eyes)

            # Torso region analysis (region below face)
            torso_y1 = min(gh, fy + fh)
            torso_y2 = min(gh, fy + int(fh * 2.8))
            torso_x1 = max(0, fx - int(fw * 0.4))
            torso_x2 = min(gw, fx + fw + int(fw * 0.4))
            torso = gn[torso_y1:torso_y2, torso_x1:torso_x2]

            if torso.size > 0:
                hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
                # Standard HSV skin detection range
                mask = cv2.inRange(hsv, np.array([0, 25, 60]), np.array([25, 255, 255]))
                skin_pct = float(np.sum(mask > 0)) / mask.size

        # 2. Full Body check if face is small or undetected
        body_detected = False
        if not face_detected or face_ratio < 0.12:
            bodies = self.fullbody_cascade.detectMultiScale(gray, 1.1, 3, minSize=(100, 200))
            body_detected = len(bodies) > 0

        # 3. Wardrobe color variance
        color_std = float(np.std(gn))

        # 4. Tier Classification & Scoring
        assigned_tier = None
        score = 0.0

        if face_detected and (face_ratio >= 0.22 or fw_orig >= 450):
            # TIER 1: Identity Anchors (Macro & Close-Up Face)
            assigned_tier = "tier1"
            landmark_mult = 1.2 if eyes_detected >= 2 else 0.8
            score = (face_sharpness * 0.6 + min(face_ratio, 0.6) * 400.0) * landmark_mult

        elif not face_detected or face_ratio <= 0.08 or (body_detected and face_ratio < 0.11):
            # TIER 4: 3D Spatial Awareness (Full-Length & Motion)
            assigned_tier = "tier4"
            # Ranks on overall sharpness and clean vertical aspect ratio
            aspect_ratio = float(h) / float(w)
            score = global_lap * 0.6 + min(aspect_ratio, 2.0) * 50.0

        else:
            # MID-RANGE FRAMING: Discriminate between Tier 2 (Anatomy) and Tier 3 (Wardrobe)
            if skin_pct >= 0.32:
                # TIER 2: Raw Anatomy (Higher exposed skin, torso contour, natural proportions)
                assigned_tier = "tier2"
                score = global_lap * 0.4 + (skin_pct * 300.0) + (float(w * h) / 1e6) * 5.0
            else:
                # TIER 3: Wardrobe Agnosticism (Diverse clothing, fabric texture, fashion styling)
                assigned_tier = "tier3"
                score = global_lap * 0.4 + (color_std * 2.0) + (float(w * h) / 1e6) * 5.0

        return {
            "filename": os.path.basename(fpath),
            "filepath": fpath,
            "width": w,
            "height": h,
            "face_detected": face_detected,
            "face_ratio": round(face_ratio, 3),
            "face_w": fw_orig,
            "face_h": fh_orig,
            "face_sharpness": round(face_sharpness, 1),
            "global_sharpness": round(global_lap, 1),
            "skin_pct": round(skin_pct, 3),
            "tier": assigned_tier,
            "score": round(score, 1)
        }

    def run(self):
        print(f"==================================================")
        print(f"ZIT Tier-Matrix Dataset Curator")
        print(f"Input Master Pool : {self.input_dir}")
        print(f"Target Output     : {self.output_dir}")
        print(f"Target Quotas     : {self.quotas}")
        print(f"==================================================")

        if not os.path.exists(self.input_dir):
            raise FileNotFoundError(f"Input directory does not exist: {self.input_dir}")

        image_files = [f for f in os.listdir(self.input_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
        total_files = len(image_files)
        print(f"Discovered {total_files} candidate images. Analyzing on pure CPU...")

        t0 = time.time()
        categorized = {"tier1": [], "tier2": [], "tier3": [], "tier4": []}

        for idx, fname in enumerate(image_files, 1):
            fp = os.path.join(self.input_dir, fname)
            res = self.analyze_image(fp)
            if res and res["tier"]:
                categorized[res["tier"]].append(res)

            if idx % 200 == 0 or idx == total_files:
                elapsed = time.time() - t0
                print(f"  [{idx}/{total_files}] images analyzed ({idx/elapsed:.1f} imgs/sec)...")

        print("\nClassification Breakdown:")
        for t, items in categorized.items():
            print(f"  {t.upper()}: {len(items)} eligible images")

        # Sort each tier by score descending and take the quota
        tier_names = {
            "tier1": ("Tier1_Identity_Anchors", self.quotas["tier1"]),
            "tier2": ("Tier2_Raw_Anatomy", self.quotas["tier2"]),
            "tier3": ("Tier3_Wardrobe_Agnosticism", self.quotas["tier3"]),
            "tier4": ("Tier4_3D_Spatial", self.quotas["tier4"])
        }

        harvested = {}
        for tier_key, (folder_name, quota) in tier_names.items():
            pool = categorized[tier_key]
            pool.sort(key=lambda x: x["score"], reverse=True)
            selected = pool[:quota]
            harvested[tier_key] = selected
            
            dest_dir = os.path.join(self.output_dir, folder_name)
            if not self.dry_run:
                os.makedirs(dest_dir, exist_ok=True)
                for item in selected:
                    dst = os.path.join(dest_dir, item["filename"])
                    shutil.copy2(item["filepath"], dst)

        # Write metadata report
        report_data = {
            "total_scanned": total_files,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "harvested_summary": {k: len(v) for k, v in harvested.items()},
            "results": harvested
        }

        report_file = os.path.join(self.output_dir, "tier_matrix_harvest_report.json")
        if not self.dry_run:
            os.makedirs(self.output_dir, exist_ok=True)
            with open(report_file, "w", encoding="utf-8") as rf:
                json.dump(report_data, rf, indent=2)

        print(f"\nHarvest Complete in {time.time() - t0:.1f}s!")
        print(f"Report written to: {report_file}")
        return harvested


def main():
    parser = argparse.ArgumentParser(description="ZIT Tier-Matrix Dataset Curator")
    parser.add_argument("--input_dir", default=r"D:\AI\Projects\ComfyUI\input\Amy_Raw_Staging\all", help="Source pool directory")
    parser.add_argument("--output_dir", default=r"D:\AI\Projects\ComfyUI\input\Amy_Raw_Staging\Tier_Anchors", help="Destination directory")
    parser.add_argument("--t1_quota", type=int, default=15, help="Tier 1 Face Anchors quota (default: 15)")
    parser.add_argument("--t2_quota", type=int, default=10, help="Tier 2 Anatomy quota (default: 10)")
    parser.add_argument("--t3_quota", type=int, default=15, help="Tier 3 Wardrobe quota (default: 15)")
    parser.add_argument("--t4_quota", type=int, default=10, help="Tier 4 Spatial quota (default: 10)")
    parser.add_argument("--dry_run", action="store_true", help="Analyze without copying files")

    args = parser.parse_args()

    quotas = {
        "tier1": args.t1_quota,
        "tier2": args.t2_quota,
        "tier3": args.t3_quota,
        "tier4": args.t4_quota
    }

    curator = TierMatrixCurator(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        quotas=quotas,
        dry_run=args.dry_run
    )
    curator.run()


if __name__ == "__main__":
    main()

