import re
import json
from pathlib import Path

vault_dir = Path(r"D:\AI\Projects\ComfyUI\output\Phase3_Golden_Vault_450")
stats_file = vault_dir / "golden_vault_stats.json"
out_md = Path(r"C:\Users\boben\Desktop\45_Verified_Replacements.md")

with open(stats_file, "r", encoding="utf-8") as f:
    orig_manifest = {x["filename"] for x in json.load(f)}

current_vault = {p.name for p in vault_dir.glob("*.png")}
new_replacements = sorted(list(current_vault - orig_manifest))

lines = [
    "# 45 Verified Replacements (Audit & Parity Passed)",
    "These are the 45 clean images that replaced the rejected casualties in Phase3_Golden_Vault_450.",
    f"Total Replacements: {len(new_replacements)} files.",
    "",
    "| # | Tier | Filename |",
    "|:---:|:---:|:---|",
]

for i, name in enumerate(new_replacements, 1):
    tmatch = re.search(r'vespera_(T[1-5])_', name)
    t = tmatch.group(1) if tmatch else "?"
    lines.append(f"| {i} | **{t}** | `{name}` |")

out_md.write_text("\n".join(lines), encoding="utf-8")
print(f"[+] Saved {len(new_replacements)} replacements to {out_md}")

