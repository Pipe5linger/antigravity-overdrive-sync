import json
import time
from pathlib import Path

MASTER_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\Phase3_Dataset_Master")
KEEPERS_DIR = MASTER_DIR / "staged_keepers"
REJECTS_DIR = MASTER_DIR / "quarantined_rejects"
ledger_file = MASTER_DIR / "live_cull_ledger.json"
report_file = MASTER_DIR / "LIVE_HARVEST_REPORT.md"

with open(ledger_file, "r", encoding="utf-8") as f:
    ledger = json.load(f)

actual_keepers = set(f.name for f in KEEPERS_DIR.glob("*.png"))
actual_rejects = set(f.name for f in REJECTS_DIR.glob("*.png"))

goldens = len([r for r in ledger if r.get("file") in actual_keepers and r.get("status") == "GOLDEN"])
passes = len([r for r in ledger if r.get("file") in actual_keepers and r.get("status") == "PASS"])
user_culled = len([r for r in ledger if r.get("status") == "USER_CULLED"])
quarantined = len(actual_rejects)
total_kept = len(actual_keepers)

lines = [
    "# Phase 3 Live Autonomous Harvest Report (Clean Single-Vault 2026-10-10)",
    f"**Last Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
    f"**Active Keepers in Vault:** **{total_kept}** (🌟 {goldens} Golden + ✅ {passes} Pass) | **User Culled:** {user_culled} | **Quarantined:** {quarantined}",
    "",
    "| Category | Count | Criteria |",
    "|:---|:---:|:---|",
    f"| 🌟 **Golden Clones** | **{goldens}** | Parity $\\ge 0.70$ (Multi-Anchor Frontal & Profile) |",
    f"| ✅ **Pass (Curated)** | **{passes}** | Parity $0.58 - 0.69$ + Sharpness $\\ge 75$ (Anatomy, Wardrobe, Rear Views) |",
    f"| 🗑️ **User Culled (Deleted)** | **{user_culled}** | Manually deleted by Bobby during visual culling |",
    f"| ⚠️ **Quarantined Rejects** | **{quarantined}** | Low Likeness $(< 0.58)$ or Blurry ($< 75.0$) |",
    "",
    "### Top 20 Highest Likeness Assets in Active Vault:",
    "| Score | Sharpness | Match Mode | Asset Name | Tier |",
    "|:---:|:---:|:---:|:---|:---:|"
]

active_ledger = [r for r in ledger if r.get("file") in actual_keepers]
sorted_ledger = sorted(active_ledger, key=lambda x: x.get("score", 0), reverse=True)
for r in sorted_ledger[:20]:
    sharp_str = f"{r.get('sharpness', 0.0):.1f}"
    match_str = r.get("match_type", "frontal").replace("_", " ").title()
    score_str = f"{r.get('score', 0):.4f}"
    tier_str = r.get("tier", "T?")
    fname = r.get("file", "")
    lines.append(f"| **{score_str}** | {sharp_str} | {match_str} | `{fname}` | {tier_str} |")

with open(report_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Report synced with disk: {total_kept} active keepers ({goldens} golden, {passes} pass), {user_culled} user culled, {quarantined} quarantined.")
