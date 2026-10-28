import re
import shutil
from pathlib import Path
import sys

sys.path.append(r"D:\AI\Projects\antigravity-overdrive-sync\scripts\curation")
from audit_and_reroll_matrix_sweep import audit_image, load_anchors, get_face_app

vault_dir = Path(r"D:\AI\Projects\ComfyUI\output\Phase3_Golden_Vault_450")
studio_dir = Path(r"D:\AI\Projects\ComfyUI\output\Phase_3_Studio")
md_file = Path(r"C:\Users\boben\Desktop\DAIProjectsComfyUIoutputPhase3_Gold.md")

# 1. Parse all past rejected files
rejected_names = set()
with open(md_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip().replace("\\_", "_")
        m = re.search(r'(vespera_T[1-5]_[^\s"]+\.png)', line)
        if m:
            rejected_names.add(m.group(1))

# Add the 4 new ones
new_4 = [
    "vespera_T3_09_R5_Gothic_Frock_Coat_Leather_s294_00001_.png",
    "vespera_T3_12_R2_Sapphire_Velvet_Bustier_s102_00001_.png",
    "vespera_T4_10_R12_Floor_Reclining_Horizon_s765_00001_.png",
    "vespera_T5_118_R8_Wet_Ringlet_Hair_Flip_in_Bath_s518_00001_.png"
]
rejected_names.update(new_4)

# Delete the 4 rejected from vault
for bad in new_4:
    p_bad = vault_dir / bad
    if p_bad.exists():
        p_bad.unlink()
        print(f"[-] Deleted rejected file: {bad}")
    txt_bad = vault_dir / bad.replace(".png", ".txt")
    if txt_bad.exists():
        txt_bad.unlink()

anchors = load_anchors()
app = get_face_app()

vault_names = {p.name for p in vault_dir.glob("*.png")}

AVOID = [
    "pillow", "mirror", "latex", "back_view", "walk_away", "chin",
    "velvet_gown", "feline", "harness", "overhead", "frock_coat",
    "bustier", "floor_reclining", "hair_flip", "bath", "cigarette"
]

needed = {"T3": 2, "T4": 1, "T5": 1}
found_replacements = {}

for tier, count in needed.items():
    found_replacements[tier] = []
    cands = sorted(list(studio_dir.glob(f"vespera_{tier}_*_s*.png")))
    for c in cands:
        if c.name in vault_names or c.name in rejected_names:
            continue
        if any(x in c.name.lower() for x in AVOID):
            continue
        res = audit_image(c, anchors, app)
        if res["status"] == "PRISTINE" and res["metrics"]["parity"] >= 0.55:
            found_replacements[tier].append((c, res["metrics"]["parity"]))
            vault_names.add(c.name)
            if len(found_replacements[tier]) == count:
                break

print("\nDeploying 4 pristine substitutes:")
for tier, flist in found_replacements.items():
    for p, par in flist:
        dst = vault_dir / p.name
        shutil.copy2(p, dst)
        print(f"   [✓] Substituted [{tier}]: {p.name} (Parity: {par:.3f})")

final_pngs = list(vault_dir.glob("*.png"))
print(f"\nFinal Vault Count: {len(final_pngs)} / 450")

