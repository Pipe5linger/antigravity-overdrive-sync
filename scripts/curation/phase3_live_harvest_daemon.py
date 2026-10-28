"""
Phase 3 Real-Time Autonomous Culling & Staging Daemon (Multi-Anchor & Sharpness Engine)
========================================================================================
Watches D:\\AI\\Projects\\ComfyUI\\output\\dataset_images for incoming renders in real-time.
- Multi-Anchor Biometric Likeness: Evaluates against Frontal, 3/4 Profile, and 90° Hard Profile.
- Optical Sharpness Guard: Evaluates Laplacian variance (rejects blurry/soft renders < 75.0).
- Rear & Spatial Silhouette Awareness: Preserves crucial back-view/spine/hair training assets.
- Live Auto-Promotion: Safely promotes rescued assets into staged_keepers and updates ledger.
"""

import sys
import time
import json
import shutil
from pathlib import Path

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

WATCH_DIR = Path(r"D:\AI\Projects\ComfyUI\output\dataset_images")
MASTER_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\Phase3_Dataset_Master")
KEEPERS_DIR = MASTER_DIR / "staged_keepers"
REJECTS_DIR = MASTER_DIR / "quarantined_rejects"
LEDGER_FILE = MASTER_DIR / "live_cull_ledger.json"
REPORT_FILE = MASTER_DIR / "LIVE_HARVEST_REPORT.md"

for d in [MASTER_DIR, KEEPERS_DIR, REJECTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Candidate paths for multi-anchors
FRONTAL_CANDIDATES = [
    Path(r"D:\AI\Projects\ComfyUI\output\miscellaneous\phase3_lora_sweep\vespera_R1_T1_01_Direct_Frontal_Portrait_s0_00001_.png"),
    Path(r"D:\AI\Projects\ComfyUI\output\phase3_lora_sweep\vespera_R1_T1_01_Direct_Frontal_Portrait_s0_00001_.png"),
    Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\anchor_face_v6_canonical.png"),
]

PROFILE_34_CANDIDATES = [
    KEEPERS_DIR / "vespera_R4_T1_02_Three_Quarter_Profile_Right_s152_00001_.png",
    WATCH_DIR / "vespera_R4_T1_02_Three_Quarter_Profile_Right_s152_00001_.png",
]

PROFILE_90_CANDIDATES = [
    KEEPERS_DIR / "vespera_R6_T1_05_Full_Profile_Right_Silhouette_s253_00001_.png",
    WATCH_DIR / "vespera_R6_T1_05_Full_Profile_Right_Silhouette_s253_00001_.png",
]

_FACE_APP = None
_ANCHOR_EMBS = {}

def get_face_app():
    global _FACE_APP
    if _FACE_APP is None:
        from insightface.app import FaceAnalysis
        print("  [AI] Initializing InsightFace buffalo_l on CPU...")
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.20)
        _FACE_APP = app
    return _FACE_APP

def load_normed_emb(img_path):
    import cv2
    app = get_face_app()
    img = cv2.imread(str(img_path))
    if img is None:
        return None
    faces = app.get(img)
    if not faces:
        return None
    largest_face = sorted(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0]
    return largest_face.normed_embedding

def get_multi_anchors():
    global _ANCHOR_EMBS
    if not _ANCHOR_EMBS:
        # 1. Frontal
        p_front = next((p for p in FRONTAL_CANDIDATES if p.exists()), None)
        if p_front:
            emb = load_normed_emb(p_front)
            if emb is not None:
                _ANCHOR_EMBS["frontal"] = emb
                print(f"  [+] Loaded Frontal Anchor: {p_front.name}")

        # 2. 3/4 Profile
        p_34 = next((p for p in PROFILE_34_CANDIDATES if p.exists()), None)
        if p_34:
            emb = load_normed_emb(p_34)
            if emb is not None:
                _ANCHOR_EMBS["profile_34"] = emb
                print(f"  [+] Loaded 3/4 Profile Anchor: {p_34.name}")

        # 3. 90 Profile
        p_90 = next((p for p in PROFILE_90_CANDIDATES if p.exists()), None)
        if p_90:
            emb = load_normed_emb(p_90)
            if emb is not None:
                _ANCHOR_EMBS["profile_90"] = emb
                print(f"  [+] Loaded 90° Hard Profile Anchor: {p_90.name}")

        if not _ANCHOR_EMBS:
            raise RuntimeError("Fatal: Could not load any reference anchor embeddings!")

    return _ANCHOR_EMBS

def compute_sharpness(img_path):
    import cv2
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())

def evaluate_image(pf, app, anchors):
    import cv2
    import numpy as np

    tier = 'T1' if '_T1_' in pf.name else ('T2' if '_T2_' in pf.name else ('T3' if '_T3_' in pf.name else 'T4'))
    sharpness = compute_sharpness(pf)
    if sharpness < 75.0:
        return {
            "score": 0.0,
            "sharpness": sharpness,
            "status": "REJECT",
            "reason": "BLURRY",
            "match_type": "none",
            "tier": tier
        }

    img = cv2.imread(str(pf))
    if img is None:
        return None

    faces = app.get(img)
    if faces and len(faces) > 1:
        return {
            "score": 0.0,
            "sharpness": sharpness,
            "status": "REJECT",
            "reason": "MULTIPLE_FACES",
            "match_type": "none",
            "tier": tier
        }

    best_score = 0.0
    best_match = "none"

    if faces:
        f = sorted(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0]
        norm_emb = f.normed_embedding

        for a_name, a_emb in anchors.items():
            sim = float(np.dot(norm_emb, a_emb))
            if sim > best_score:
                best_score = sim
                best_match = a_name

    tier = 'T1' if '_T1_' in pf.name else ('T2' if '_T2_' in pf.name else ('T3' if '_T3_' in pf.name else 'T4'))
    is_rear = any(k in pf.name.lower() for k in ['back', 'rear', 'spine', 'walk_away', 'ringlet_volume'])

    # Decision Matrix
    if best_score >= 0.70:
        status = "GOLDEN"
        reason = f"MATCH_{best_match.upper()}"
    elif best_score >= 0.65 and tier == 'T1':
        status = "PASS"
        reason = f"T1_MATCH_{best_match.upper()}"
    elif best_score >= 0.58 and tier in ['T2', 'T3', 'T4']:
        status = "PASS"
        reason = f"BODY_FASHION_MATCH_{best_match.upper()}"
    elif is_rear and sharpness >= 80.0:
        status = "PASS"
        best_score = max(best_score, 0.65)
        reason = "REAR_SILHOUETTE_PASS"
    else:
        status = "REJECT"
        reason = "LOW_PARITY" if best_score > 0 else "NO_FACE_DETECTED"

    return {
        "score": best_score,
        "sharpness": sharpness,
        "status": status,
        "reason": reason,
        "match_type": best_match,
        "tier": tier
    }

def update_report(ledger):
    total = len(ledger)
    goldens = len([r for r in ledger if r['status'] == 'GOLDEN'])
    passes = len([r for r in ledger if r['status'] == 'PASS'])
    rejects = len([r for r in ledger if r['status'] == 'REJECT'])

    lines = [
        "# Phase 3 Live Autonomous Harvest Report (Multi-Anchor)",
        f"**Last Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Processed:** {total} | **Kept (Golden + Pass):** {goldens + passes} | **Quarantined:** {rejects}",
        "",
        "| Category | Count | Criteria |",
        "|:---|:---:|:---|",
        f"| 🌟 **Golden Clones** | **{goldens}** | Parity $\\ge 0.70$ (Multi-Anchor Frontal & Profile) |",
        f"| ✅ **Pass (Curated)** | **{passes}** | Parity $0.58 - 0.69$ + Sharpness $\\ge 75$ (Anatomy, Wardrobe, Rear Views) |",
        f"| ⚠️ **Quarantined** | **{rejects}** | Low Likeness $(< 0.58)$ or Blurry ($< 75.0$) |",
        "",
        "### Top 20 Highest Likeness Assets Harvested:",
        "| Score | Sharpness | Match Mode | Asset Name | Tier |",
        "|:---:|:---:|:---:|:---|:---:|"
    ]

    sorted_ledger = sorted([r for r in ledger if r['status'] != 'REJECT'], key=lambda x: x['score'], reverse=True)
    for r in sorted_ledger[:20]:
        sharp_str = f"{r.get('sharpness', 0.0):.1f}"
        match_str = r.get('match_type', 'frontal').replace('_', ' ').title()
        lines.append(f"| **{r['score']:.4f}** | {sharp_str} | {match_str} | `{r['file']}` | {r.get('tier', 'T?')} |")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def salvage_quarantine(app, anchors, ledger, processed):
    print("\n🔍 Auditing quarantine vault with multi-anchor engine...")
    rescued = 0
    quarantine_files = list(REJECTS_DIR.glob("*.png"))
    ledger_dict = {r["file"]: r for r in ledger}

    for qf in quarantine_files:
        res = evaluate_image(qf, app, anchors)
        if res and res["status"] in ["GOLDEN", "PASS"]:
            rescued += 1
            dest = KEEPERS_DIR / qf.name
            shutil.move(qf, dest)
            print(f"  ✨ Rescued: {res['score']:.4f} ({res['reason']}) -> {qf.name[:45]}...")

            entry = {
                "file": qf.name,
                "score": res["score"],
                "sharpness": res["sharpness"],
                "status": res["status"],
                "reason": res["reason"],
                "match_type": res["match_type"],
                "tier": res["tier"],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            ledger_dict[qf.name] = entry
            processed.add(qf.name)

    if rescued > 0:
        new_ledger = list(ledger_dict.values())
        with open(LEDGER_FILE, "w", encoding="utf-8") as f:
            json.dump(new_ledger, f, indent=2)
        update_report(new_ledger)
        print(f"[+] Successfully rescued {rescued} golden & pass assets from quarantine!\n")
    else:
        print("[+] Quarantine audit complete. No pending rescues.\n")

    return list(ledger_dict.values())

def main():
    print("=" * 80)
    print("🔥 Phase 3 Real-Time Multi-Anchor Autonomous Culling Daemon Online")
    print(f"Watching Directory : {WATCH_DIR}")
    print(f"Keepers Staging    : {KEEPERS_DIR}")
    print(f"Quarantine Rejects : {REJECTS_DIR}")
    print("=" * 80)

    app = get_face_app()
    anchors = get_multi_anchors()

    ledger = []
    if LEDGER_FILE.exists():
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            print(f"[+] Loaded {len(ledger)} previous entries from ledger.")
        except Exception:
            pass

    processed = set(r["file"] for r in ledger)

    print("\n[+] Daemon listening for incoming renders... (Press Ctrl+C to stop)")
    while True:
        try:
            current_files = sorted(list(WATCH_DIR.glob("*.png")), key=lambda x: x.stat().st_mtime)
            today_str = time.strftime("%Y-%m-%d")
            new_files = [f for f in current_files if f.name not in processed]

            for pf in new_files:
                # Strictly enforce today's generation date
                try:
                    file_date = time.strftime("%Y-%m-%d", time.localtime(pf.stat().st_mtime))
                    if file_date != today_str:
                        processed.add(pf.name)
                        continue
                except Exception:
                    pass

                time.sleep(0.5)
                res = evaluate_image(pf, app, anchors)
                if res is None:
                    continue

                if res["status"] in ["GOLDEN", "PASS"]:
                    dest = KEEPERS_DIR / pf.name
                    shutil.move(pf, dest)
                else:
                    dest = REJECTS_DIR / pf.name
                    shutil.move(pf, dest)

                entry = {
                    "file": pf.name,
                    "score": res.get("score", 0.0),
                    "sharpness": res.get("sharpness", 0.0),
                    "status": res.get("status", "REJECT"),
                    "reason": res.get("reason", "UNKNOWN"),
                    "match_type": res.get("match_type", "none"),
                    "tier": res.get("tier", "T?"),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                ledger.append(entry)
                processed.add(pf.name)

                badge = "🌟 GOLDEN" if res["status"] == "GOLDEN" else ("✅ PASS" if res["status"] == "PASS" else "⚠️ REJECT")
                print(f"[{time.strftime('%H:%M:%S')}] {badge} ({res['score']:.4f} | Sharp:{res['sharpness']:.1f} | {res['match_type']}) -> {pf.name[:40]}...")

                with open(LEDGER_FILE, "w", encoding="utf-8") as f:
                    json.dump(ledger, f, indent=2)

                update_report(ledger)

            time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n[-] Daemon stopped by user.")
            break
        except Exception as e:
            import traceback
            print(f"[-] Error in daemon loop: {e}")
            traceback.print_exc()
            time.sleep(2.0)

if __name__ == "__main__":
    main()
