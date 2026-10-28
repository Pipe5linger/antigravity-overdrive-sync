"""
Vespera Matrix Sweep Forensic Auditor & Auto-Healer
===================================================
Automated post-sweep quality assurance & selective re-roll engine for 2,600-image dataset sweeps:
1. Scans all rendered images across Phase 3 Studio.
2. Extracts deterministic Seed, Tier, Round, Slot, and Take index.
3. Evaluates:
   - Facial Likeness & Parity (InsightFace Buffalo_L CPU against master reference anchors)
   - Missed Face Detection on frontal/portrait slots
   - Specular Highlight Burnout (> 1.5% blown pixels)
   - Severe Blur / Smear (Laplacian Variance < 80.0)
   - Dermal Saturation / Orange Tone Overshoot
4. Generates:
   - SWEEP_AUDIT_REPORT.md (categorized defect report)
   - sweep_defects_ledger.json (exact defective seed list & Take 2 re-roll targets)
5. Optional Auto-Heal Mode (--rerun):
   - Automatically queues only the defective slots on ComfyUI shifted by +2600 (Take 2)
   - Preserves all pristine renders while systematically replacing defects!
"""

import sys
import os
import re
import json
import time
import argparse
import urllib.request
from pathlib import Path

import cv2
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

COMFY_URL = "http://127.0.0.1:8188"
PROJECT_DIR = Path(r"D:\AI\Projects")
COMFY_DIR = PROJECT_DIR / "ComfyUI"
STUDIO_OUTPUT_DIR = COMFY_DIR / "output" / "Phase_3_Studio"

# Anchor Vault
ANCHOR_DIR = COMFY_DIR / "output" / "reference_anchors" / "face"
if not ANCHOR_DIR.exists():
    ANCHOR_DIR = PROJECT_DIR / "ai-toolkit" / "vespera_anchors"

MASTER_ANCHORS = {
    "frontal": ANCHOR_DIR / "anchor_frontal.png",
    "low_angle": ANCHOR_DIR / "anchor_low_angle.png",
    "profile_left": ANCHOR_DIR / "anchor_profile_left.png",
    "profile_right": ANCHOR_DIR / "anchor_profile_right.png",
}

# Parity Pass Thresholds per Tier
TIER_PARITY_THRESHOLDS = {
    "T1": 0.55,  # Close-up editorial portraits require strong identity
    "T2": 0.50,  # Intimate boudoir & anatomy
    "T3": 0.48,  # Couture wardrobe & drape
    "T4": 0.35,  # Full-body perspective & distance
    "T5": 0.45,  # Explicit uninhibited boudoir
}

# Slots that intentionally feature rear/back views or floor overheads without visible face
BACK_VIEW_WHITELIST = [
    "back_view", "looking_back_over_shoulder", "walk_away", "behind",
    "floor_inverted", "t4_02", "t4_03", "t2_04"
]

_FACE_APP = None
_ANCHOR_EMBS = {}


def get_face_app():
    global _FACE_APP
    if _FACE_APP is None:
        from insightface.app import FaceAnalysis
        print("  [AI] Initializing InsightFace buffalo_l on CPU for forensic analysis...")
        _FACE_APP = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _FACE_APP.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.18)
    return _FACE_APP


def load_anchors():
    global _ANCHOR_EMBS
    if _ANCHOR_EMBS:
        return _ANCHOR_EMBS
    app = get_face_app()
    for key, path in MASTER_ANCHORS.items():
        if path.exists():
            img = cv2.imread(str(path))
            if img is not None:
                faces = app.get(img)
                if faces:
                    f = max(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
                    _ANCHOR_EMBS[key] = f.normed_embedding
                    print(f"  [Anchors] Loaded {key} master identity anchor.")
    return _ANCHOR_EMBS


def comfy_api(endpoint: str, method: str = "GET", body: dict = None, timeout: float = 30.0):
    data = json.dumps(body).encode("utf-8") if body else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(f"{COMFY_URL}{endpoint}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_filename_meta(p: Path) -> dict:
    """Extracts Tier, Slot, Round, Take, and Seed from standardized filename."""
    name = p.stem
    meta = {
        "path": p,
        "filename": p.name,
        "tier": "T1",
        "slot": 1,
        "round": 1,
        "take": 1,
        "seed": 0,
        "slug": name,
    }
    
    # Extract seed: _s1004_ or _s1_
    smatch = re.search(r'_s(\d+)_', name)
    if smatch:
        meta["seed"] = int(smatch.group(1))

    # Extract tier: T1 to T5
    tmatch = re.search(r'vespera_(T[1-5])_', name, re.IGNORECASE)
    if tmatch:
        meta["tier"] = tmatch.group(1).upper()

    # Extract round: _R1_ or _R20_
    rmatch = re.search(r'_R(\d+)_', name)
    if rmatch:
        meta["round"] = int(rmatch.group(1))

    # Extract take: _Take2_
    tkmatch = re.search(r'_Take(\d+)_', name)
    if tkmatch:
        meta["take"] = int(tkmatch.group(1))

    # Fallback seed calculation if _s\d+_ not in filename
    if meta["seed"] == 0:
        # Check slot index: e.g. T1_01 -> slot 1
        slot_match = re.search(r'T[1-5]_(\d+)_', name)
        if slot_match:
            meta["slot"] = int(slot_match.group(1))

    return meta


def audit_image(p: Path, anchors: dict, app) -> dict:
    meta = parse_filename_meta(p)
    tier = meta["tier"]
    slug = meta["slug"].lower()
    
    img = cv2.imread(str(p))
    if img is None:
        return {"status": "FAIL", "defect": "CORRUPT_IMAGE", "meta": meta, "metrics": {}}

    h, w, _ = img.shape
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. Blur / Sharpness check
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    
    # 2. Specular / Highlight blowout check
    blown_ratio = float(np.mean(gray > 245) * 100.0)

    # 3. Facial detection & parity
    faces = app.get(img)
    best_sim = 0.0
    face_found = len(faces) > 0
    mean_r, mean_g, mean_b, olive_ratio = 0.0, 0.0, 0.0, 0.0

    if face_found:
        f = max(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
        emb = f.normed_embedding
        sims = [float(np.dot(a_emb, emb)) for a_emb in anchors.values()]
        best_sim = max(sims) if sims else 0.0

        # Facial skin tone metrics
        bbox = [int(max(0, x)) for x in f.bbox]
        fcrop = img[bbox[1]:bbox[3], bbox[0]:bbox[2]]
        if fcrop.size > 0:
            face_rgb = cv2.cvtColor(fcrop, cv2.COLOR_BGR2RGB)
            mean_r, mean_g, mean_b = np.mean(face_rgb, axis=(0,1))
            olive_ratio = float(mean_g / max(1.0, mean_r))

    # Evaluate defects
    defects = []
    
    # Is this a known rear/back view?
    is_back_view = any(b in slug for b in BACK_VIEW_WHITELIST)

    if not face_found and not is_back_view:
        # Frontal/boudoir shot completely missed face detection
        if tier in ("T1", "T2"):
            defects.append("MISSING_FACE")
    elif face_found:
        if len(faces) > 1:
            defects.append(f"PHANTOM_FACE (Count={len(faces)})")
        min_parity = TIER_PARITY_THRESHOLDS.get(tier, 0.45)
        if best_sim < min_parity and not is_back_view:
            defects.append(f"LOW_PARITY ({best_sim:.3f} < {min_parity:.2f})")

    if blown_ratio > 1.5:
        defects.append(f"SPECULAR_BURNOUT ({blown_ratio:.1f}%)")

    if lap_var < 75.0:
        defects.append(f"BLUR_DEFECT ({lap_var:.1f})")

    if face_found and olive_ratio < 0.62:
        defects.append(f"ORANGE_OVERSHOOT (Olive={olive_ratio:.2f})")

    status = "PRISTINE" if not defects else "DEFECT"
    
    return {
        "status": status,
        "defects": defects,
        "meta": meta,
        "metrics": {
            "parity": best_sim,
            "sharpness": lap_var,
            "specular": blown_ratio,
            "olive_ratio": olive_ratio,
            "faces": len(faces),
            "face_found": face_found
        }
    }


def queue_rerolls(defective_items: list, cycle_length: int = 1300):
    """Submits Take 2 re-roll jobs for defective seeds via ComfyUI API."""
    from PIL import Image

    print(f"\n[🚀 Auto-Heal] Connecting to ComfyUI on {COMFY_URL}...")
    try:
        stats = comfy_api("/system_stats")
        print(f"  [ComfyUI] 🟢 Online (v{stats.get('system', {}).get('comfyui_version', '?')})")
    except Exception as e:
        print(f"[-] Cannot connect to ComfyUI at {COMFY_URL}: {e}")
        return

    print(f"[🚀 Auto-Heal] Queuing Take 2 re-rolls for {len(defective_items)} defective slots (cycle offset: +{cycle_length})...")
    queued = 0
    skipped = 0

    for item in defective_items:
        meta = item["meta"]
        orig_seed = meta["seed"]
        take_num = meta["take"] + 1
        reroll_seed = orig_seed + cycle_length
        tier = meta["tier"]
        defect_str = ", ".join(item["defects"])
        img_path = meta["path"]

        # Check if Take 2 already exists
        existing = list(STUDIO_OUTPUT_DIR.glob(f"*_s{reroll_seed}_*.png"))
        if existing:
            print(f"  ⏭️ Seed {orig_seed} ➔ Seed {reroll_seed} already rendered: {existing[0].name}")
            skipped += 1
            continue

        try:
            im = Image.open(str(img_path))
            prompt_raw = im.info.get("prompt")
            if not prompt_raw:
                # Fallback to any file with prompt
                sample = next(STUDIO_OUTPUT_DIR.glob("vespera_*_s1_*.png"), None)
                if sample:
                    im_sample = Image.open(str(sample))
                    prompt_raw = im_sample.info.get("prompt")
            
            if not prompt_raw:
                print(f"  [-] Could not extract prompt graph for seed {orig_seed}")
                continue

            prompt_graph = json.loads(prompt_raw)
            # Update seeds for PoseActionNode, PromptWorkstation, and KSampler
            if "5" in prompt_graph:
                prompt_graph["5"]["inputs"]["master_seed"] = reroll_seed
            if "6" in prompt_graph:
                prompt_graph["6"]["inputs"]["master_seed"] = reroll_seed
            if "10" in prompt_graph:
                prompt_graph["10"]["inputs"]["seed"] = reroll_seed

            # Dispatch to ComfyUI
            body = {"prompt": prompt_graph, "client_id": "auto_healer"}
            resp = comfy_api("/prompt", method="POST", body=body)
            if resp.get("prompt_id"):
                print(f"  • Queued Seed {orig_seed:4d} ➔ Seed {reroll_seed:4d} [{tier} Take {take_num}] :: Reason: {defect_str}")
                queued += 1
            else:
                print(f"  [-] Failed to queue seed {orig_seed}: {resp}")
        except Exception as e:
            print(f"  [-] Error queuing seed {orig_seed}: {e}")

    print(f"\n[+] Successfully dispatched {queued} selective healing jobs to the ComfyUI queue! ({skipped} already rendered)")


def main():
    parser = argparse.ArgumentParser(description="Vespera Matrix Sweep Forensic Auditor & Auto-Healer")
    parser.add_argument("--dir", default=str(STUDIO_OUTPUT_DIR), help="Directory containing sweep renders")
    parser.add_argument("--pattern", default="vespera_*_s*.png", help="File matching pattern")
    parser.add_argument("--cycle-length", type=int, default=1300, help="Total cycle seeds for Take offset (default: 1300)")
    parser.add_argument("--rerun", action="store_true", help="Automatically submit Take 2 re-roll jobs to ComfyUI")
    parser.add_argument("--dry-run", action="store_true", help="Show defect re-roll list without dispatching")
    parser.add_argument("--from-ledger", action="store_true", help="Instantly dispatch re-rolls from existing sweep_defects_ledger.json without re-auditing")
    args = parser.parse_args()

    target_dir = Path(args.dir)
    if not target_dir.exists():
        print(f"[-] Directory {target_dir} does not exist.")
        return

    ledger_path = target_dir / "sweep_defects_ledger.json"
    if args.from_ledger:
        if not ledger_path.exists():
            print(f"[-] Ledger not found at {ledger_path}")
            return
        items_raw = json.loads(ledger_path.read_text(encoding="utf-8"))
        # Reconstruct item format for queue_rerolls
        reconstruct = []
        for it in items_raw:
            reconstruct.append({
                "defects": it.get("defects", []),
                "meta": {
                    "path": target_dir / it["filename"],
                    "filename": it["filename"],
                    "seed": it["seed"],
                    "tier": it["tier"],
                    "round": it["round"],
                    "take": it.get("take", 1),
                }
            })
        print(f"[*] Loaded {len(reconstruct)} defect records from ledger.")
        queue_rerolls(reconstruct, cycle_length=args.cycle_length)
        return

    files = sorted(list(target_dir.glob(args.pattern)), key=lambda p: p.stat().st_mtime)
    if not files:
        print(f"[-] No images found matching '{args.pattern}' in {target_dir}")
        return

    print("=" * 80)
    print(f"🔍 VESPERA MATRIX SWEEP FORENSIC AUDITOR")
    print(f"   Target Directory : {target_dir}")
    print(f"   Total Images     : {len(files)}")
    print(f"   Cycle Length     : {args.cycle_length} (Take Offset)")
    print(f"   Auto-Heal Mode   : {'ENABLED (--rerun)' if args.rerun else 'AUDIT ONLY'}")
    print("=" * 80)

    anchors = load_anchors()
    app = get_face_app()

    results = []
    defects_count = 0
    pristine_count = 0

    print(f"\n[Audit] Inspecting {len(files)} renders...")
    t0 = time.time()
    
    for i, p in enumerate(files, 1):
        res = audit_image(p, anchors, app)
        results.append(res)
        
        if res["status"] == "PRISTINE":
            pristine_count += 1
            status_char = "✓"
        else:
            defects_count += 1
            status_char = "❌"
            defects_str = ", ".join(res["defects"])
            print(f"  [{i:4d}/{len(files)}] {status_char} Seed {res['meta']['seed']:5d} [{res['meta']['tier']}] :: {defects_str} ({p.name})")

        if i % 100 == 0:
            print(f"  ... audited {i}/{len(files)} frames ({pristine_count} pristine, {defects_count} flagged) ...")

    elapsed = time.time() - t0
    pristine_pct = (pristine_count / len(files)) * 100.0 if files else 0.0

    print("\n" + "=" * 80)
    print("📊 SWEEP AUDIT COMPLETE")
    print(f"   Audited Images   : {len(files)} frames in {elapsed:.1f}s ({len(files)/max(0.1, elapsed):.1f} fps)")
    print(f"   🏆 Pristine     : {pristine_count} ({pristine_pct:.1f}%)")
    print(f"   ⚠️ Defective     : {defects_count} ({100.0 - pristine_pct:.1f}%)")
    print("=" * 80)

    # Compile defect ledger
    defective_items = [r for r in results if r["status"] == "DEFECT"]
    ledger_path = target_dir / "sweep_defects_ledger.json"
    report_path = target_dir / "SWEEP_AUDIT_REPORT.md"

    # Save JSON ledger
    serializable = []
    for item in defective_items:
        meta = item["meta"]
        serializable.append({
            "filename": meta["filename"],
            "seed": meta["seed"],
            "tier": meta["tier"],
            "round": meta["round"],
            "take": meta["take"],
            "reroll_seed": meta["seed"] + args.cycle_length,
            "defects": item["defects"],
            "metrics": item["metrics"]
        })
    ledger_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\n[+] Saved machine-readable defect ledger: {ledger_path}")

    # Generate Markdown Report
    md_lines = [
        f"# Vespera Matrix Sweep Forensic Audit Report",
        f"**Audit Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%S')}  |  **Total Audited:** {len(files)}",
        f"**Pristine Pass Rate:** {pristine_count}/{len(files)} ({pristine_pct:.1f}%)  |  **Defects Flagged:** {defects_count}",
        "",
        "---",
        "",
        "## Defective Seed Catalog (Targeted Re-Rolls)",
        "",
        "| Original Seed | Tier | Round | Current Take | **Re-roll Seed (Take 2)** | Flagged Defect | Parity | Specular | Sharpness | Filename |",
        "|:---:|:---:|:---:|:---:|:---:|:---|:---:|:---:|:---:|:---|",
    ]
    for d in serializable[:200]:  # Top 200 in markdown
        m = d["metrics"]
        md_lines.append(
            f"| `{d['seed']}` | **{d['tier']}** | R{d['round']} | Take {d['take']} | **`{d['reroll_seed']}`** | "
            f"{', '.join(d['defects'])} | {m.get('parity', 0.0):.3f} | {m.get('specular', 0.0):.1f}% | {m.get('sharpness', 0.0):.1f} | `{d['filename']}` |"
        )
    if len(serializable) > 200:
        md_lines.append(f"\n*... and {len(serializable) - 200} more defect records saved in sweep_defects_ledger.json*")

    report_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[+] Saved comprehensive markdown report: {report_path}")

    if args.rerun:
        queue_rerolls(defective_items, cycle_length=args.cycle_length)
    elif defective_items:
        print(f"\n[💡 Tip] To automatically queue Take 2 re-rolls for all {len(defective_items)} flawed seeds, run:")
        print(f"  python {Path(__file__).resolve()} --rerun")


if __name__ == "__main__":
    main()

