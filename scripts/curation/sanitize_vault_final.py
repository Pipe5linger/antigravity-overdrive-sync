import sys
import re
import shutil
from pathlib import Path

sys.path.append(r"D:\AI\Projects\antigravity-overdrive-sync\scripts\curation")
from audit_and_reroll_matrix_sweep import audit_image, load_anchors, get_face_app

vault_dir = Path(r"D:\AI\Projects\ComfyUI\output\Phase3_Golden_Vault_450")
studio_dir = Path(r"D:\AI\Projects\ComfyUI\output\Phase_3_Studio")
md_file = Path(r"C:\Users\boben\Desktop\DAIProjectsComfyUIoutputPhase3_Gold.md")

# 1. Parse ALL rejected files
rejected_names = set()
with open(md_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip().replace("\\_", "_")
        m = re.search(r'(vespera_T[1-5]_[^\s"]+\.png)', line)
        if m:
            rejected_names.add(m.group(1))

print(f"[*] Total blacklisted filenames from Desktop file: {len(rejected_names)}")

anchors = load_anchors()
app = get_face_app()

vault_names = {p.name for p in vault_dir.glob("*.png")}
in_vault = vault_names.intersection(rejected_names)
print(f"[*] Rejected files currently in vault: {len(in_vault)}")

AVOID = ["pillow", "mirror", "latex", "back_view", "walk_away", "chin", "velvet_gown", "feline", "harness", "overhead"]

for bad_name in in_vault:
    t = re.search(r'vespera_(T[1-5])_', bad_name).group(1)
    p_bad = vault_dir / bad_name
    if p_bad.exists():
        p_bad.unlink()
    txt = vault_dir / bad_name.replace(".png", ".txt")
    if txt.exists():
        txt.unlink()
    vault_names.discard(bad_name)

    candidates = sorted(list(studio_dir.glob(f"vespera_{t}_*_s*.png")))
    found = None
    for cand in candidates:
        if cand.name in vault_names or cand.name in rejected_names:
            continue
        if any(x in cand.name.lower() for x in AVOID):
            continue
        res = audit_image(cand, anchors, app)
        if res["status"] == "PRISTINE":
            found = cand
            break

    if found:
        shutil.copy2(found, vault_dir / found.name)
        vault_names.add(found.name)
        par = res["metrics"]["parity"]
        print(f"   [✓] Clean replacement for {bad_name} ➔ {found.name} (Parity: {par:.3f})")

# Final verification
remaining_bad = {p.name for p in vault_dir.glob("*.png")}.intersection(rejected_names)
print(f"\n[*] Final verification: Remaining rejected files in vault = {len(remaining_bad)}")
print(f"[*] Total PNGs in vault: {len(list(vault_dir.glob('*.png')))}")

