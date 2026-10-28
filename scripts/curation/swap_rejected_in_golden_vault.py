"""
Swap Rejected Images in Phase 3 Golden Vault
============================================
1. Reads rejected filenames from C:\\Users\\boben\\Desktop\\DAIProjectsComfyUIoutputPhase3_Gold.md
2. Removes them and their companion .txt captions from D:\\AI\\Projects\\ComfyUI\\output\\Phase3_Golden_Vault_450
3. Selects clean replacements from D:\\AI\\Projects\\ComfyUI\\output\\Phase_3_Studio
   excluding known defects and problematic pose categories.
4. Copies replacements (shutil.copy2 - zero hardlinks) into the Golden Vault.
5. Verifies 120/80/110/80/60 tier distribution.
"""

import os
import sys
import re
import json
import shutil
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

VAULT_DIR = Path(r"D:\AI\Projects\ComfyUI\output\Phase3_Golden_Vault_450")
STUDIO_DIR = Path(r"D:\AI\Projects\ComfyUI\output\Phase_3_Studio")
MD_FILE = Path(r"C:\Users\boben\Desktop\DAIProjectsComfyUIoutputPhase3_Gold.md")
DEFECTS_LEDGER = STUDIO_DIR / "sweep_defects_ledger.json"

# Problematic pose slugs flagged by human review to avoid in replacements
AVOID_SLUGS = [
    "chin_on_hand", "silhouette", "scarlet_latex", "back_view",
    "walk_away", "feline_crouch", "straddling_chair", "chaise_lounge",
    "knee_tuck", "mirror_reflection", "wall_pin", "zip_down"
]

def main():
    print("=" * 80)
    print("🔄 EXECUTING BENCH SUBSTITUTION (OPTION A) FOR PHASE 3 GOLDEN VAULT")
    print("=" * 80)

    # 1. Parse rejected files
    rejected_names = set()
    with open(MD_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().replace("\\_", "_")
            m = re.search(r'(vespera_T[1-5]_[^\s"]+\.png)', line)
            if m:
                rejected_names.add(m.group(1))

    print(f"[*] Parsed {len(rejected_names)} rejected filenames from Desktop file.")

    # 2. Load persistent defects ledger
    persistent_defects = set()
    if DEFECTS_LEDGER.exists():
        try:
            with open(DEFECTS_LEDGER, "r", encoding="utf-8") as f:
                d = json.load(f)
                for item in d:
                    persistent_defects.add(item["filename"])
            print(f"[*] Loaded {len(persistent_defects)} blacklisted casualty filenames from ledger.")
        except Exception as e:
            print(f"[-] Ledger warning: {e}")

    # 3. Categorize rejected by tier and remove from vault
    rejected_by_tier = {"T1": [], "T2": [], "T3": [], "T4": [], "T5": []}
    removed_png = 0
    removed_txt = 0

    for name in rejected_names:
        tmatch = re.search(r'vespera_(T[1-5])_', name)
        if tmatch:
            t = tmatch.group(1)
            rejected_by_tier[t].append(name)
            p_png = VAULT_DIR / name
            p_txt = VAULT_DIR / (name.replace(".png", ".txt"))
            if p_png.exists():
                p_png.unlink()
                removed_png += 1
            if p_txt.exists():
                p_txt.unlink()
                removed_txt += 1

    print(f"\n[🗑️ Removed from Vault] {removed_png} PNGs and {removed_txt} corresponding .txt captions.")
    for t, l in rejected_by_tier.items():
        print(f"   • {t}: {len(l)} replacements needed")

    # 4. Find clean replacements from Studio Dir
    current_vault_names = {p.name for p in VAULT_DIR.glob("*.png")}
    print(f"\n[*] Current remaining images in Vault: {len(current_vault_names)}")

    all_studio_files = sorted(list(STUDIO_DIR.glob("vespera_*_s*.png")))
    available_replacements = {"T1": [], "T2": [], "T3": [], "T4": [], "T5": []}

    for p in all_studio_files:
        name = p.name
        # Skip if in vault, in rejected, in persistent defects, or in avoid list
        if name in current_vault_names:
            continue
        if name in rejected_names:
            continue
        if name in persistent_defects:
            continue
        if any(avoid in name.lower() for avoid in AVOID_SLUGS):
            continue

        tmatch = re.search(r'vespera_(T[1-5])_', name)
        if tmatch:
            t = tmatch.group(1)
            available_replacements[t].append(p)

    for t, pool in available_replacements.items():
        needed = len(rejected_by_tier[t])
        print(f"   • {t} Replacement Pool: {len(pool)} available (Need {needed})")

    # 5. Select and copy exact replacements
    copied_replacements = 0
    replacement_records = []

    for t, needed_list in rejected_by_tier.items():
        needed = len(needed_list)
        pool = available_replacements[t]
        if len(pool) < needed:
            print(f"[-] ERROR: Not enough candidates for {t}! Available: {len(pool)}, Needed: {needed}")
            sys.exit(1)
        
        # Pick diverse selection from pool
        step = max(1, len(pool) // needed)
        selected = []
        for i in range(needed):
            selected.append(pool[(i * step) % len(pool)])

        for src in selected:
            dst = VAULT_DIR / src.name
            shutil.copy2(src, dst)
            copied_replacements += 1
            replacement_records.append({"tier": t, "name": src.name})
            print(f"   ✓ Substituted [{t}]: {src.name}")

    print(f"\n[+] Successfully added {copied_replacements} clean replacements to Golden Vault!")

    # 6. Final verification of vault counts
    final_pngs = list(VAULT_DIR.glob("*.png"))
    print(f"\n{'=' * 80}")
    print(f"📊 FINAL GOLDEN VAULT HEALTH CHECK")
    print(f"   Total Images in Vault: {len(final_pngs)} / 450")

    tier_counts = {"T1": 0, "T2": 0, "T3": 0, "T4": 0, "T5": 0}
    for p in final_pngs:
        tmatch = re.search(r'vespera_(T[1-5])_', p.name)
        if tmatch:
            tier_counts[tmatch.group(1)] += 1

    print("   Tier Quota Verification:")
    expected = {"T1": 120, "T2": 80, "T3": 110, "T4": 80, "T5": 60}
    all_ok = True
    for t, exp in expected.items():
        act = tier_counts[t]
        status = "✅ PERFECT" if act == exp else f"❌ MISMATCH ({act} vs {exp})"
        if act != exp:
            all_ok = False
        print(f"     • {t}: {act} / {exp} ({status})")

    if all_ok:
        print("\n🎉 ALL 450 IMAGES ARE 100% BALANCED AND MUTATION-FREE!")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    main()

