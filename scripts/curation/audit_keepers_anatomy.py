"""
Phase 3 Post-Sweep Anatomy & Mutation Auditor (Qwen Vision 2.5-VL)
====================================================================
Runs between generation sweeps when ComfyUI VRAM is cleared.
- Scans staged_keepers for anatomical deformities, extra limbs, fused/extra fingers, and grotesque contortions.
- Quarantines mutants to Phase3_Dataset_Master/quarantined_rejects.
- Automatically flushes Ollama VRAM to 0 MB upon completion.
"""

import os
import sys
import json
import time
import base64
import io
import shutil
import urllib.request
from pathlib import Path
from PIL import Image

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MASTER_DIR = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\Phase3_Dataset_Master")
KEEPERS_DIR = MASTER_DIR / "staged_keepers"
REJECTS_DIR = MASTER_DIR / "quarantined_rejects"
AUDIT_LEDGER_FILE = MASTER_DIR / "anatomy_audit_ledger.json"
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5vl:3b"

for d in [MASTER_DIR, KEEPERS_DIR, REJECTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def purge_ollama_vram():
    try:
        url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
        payload = {"model": OLLAMA_MODEL, "prompt": "", "keep_alive": 0}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as _:
            pass
        print("  [🧹 VRAM] Ollama memory purged to 0 MB.")
    except Exception as e:
        pass

def inspect_image(img_path):
    im = Image.open(img_path)
    im.thumbnail((512, 512))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    prompt = (
        "You are an elite anatomy and deformity inspector for photorealistic AI training images.\n"
        "Carefully inspect the human figure in this image for severe defects:\n"
        "1. Extra limbs: Are there more than 2 arms or more than 2 legs?\n"
        "2. Hand/Finger mutations: Are there extra fingers (6+ digits), fused claw fingers, or melted hands?\n"
        "3. Body contortions: Is the neck, torso, or spine broken into an impossible or grotesque deformity?\n"
        "4. Floating parts: Are there disconnected or floating body parts?\n\n"
        "If you detect ANY of these mutations, verdict is FAIL.\n"
        "If the anatomy looks natural and normal, verdict is PASS.\n\n"
        "Respond in EXACTLY this format:\n"
        "VERDICT: [PASS or FAIL]\n"
        "REASON: [None or brief description of deformity]\n"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": 0.1,
            "num_predict": 128
        }
    }

    req = urllib.request.Request(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        raw_text = result.get("response", "").strip()

    verdict = "PASS"
    reason = "None"

    for line in raw_text.splitlines():
        if line.startswith("VERDICT:"):
            v = line.split(":")[-1].strip().upper()
            if "FAIL" in v:
                verdict = "FAIL"
        elif line.startswith("REASON:"):
            reason = line.split(":", 1)[-1].strip()

    return verdict, reason, raw_text

def main():
    print("=" * 80)
    print("🔬 Vespera Phase 3 Post-Sweep Anatomy & Mutation Auditor")
    print(f"Target Keepers Dir : {KEEPERS_DIR}")
    print(f"Vision Engine      : Ollama ({OLLAMA_MODEL})")
    print("=" * 80)

    # Check Ollama connection
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3)
    except Exception:
        print(f"❌ Error: Could not connect to Ollama at {OLLAMA_URL}. Ensure Ollama is running!")
        sys.exit(1)

    ledger = {}
    if AUDIT_LEDGER_FILE.exists():
        try:
            with open(AUDIT_LEDGER_FILE, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            print(f"[+] Loaded {len(ledger)} previous audit records.")
        except Exception:
            ledger = {}

    keeper_files = sorted(list(KEEPERS_DIR.glob("*.png")), key=lambda x: x.name)
    pending_files = [f for f in keeper_files if f.name not in ledger]

    print(f"[+] Staged Keepers: {len(keeper_files)} total | Pending Audit: {len(pending_files)}")
    if not pending_files:
        print("[+] All keepers have already been audited. Nothing to process!")
        purge_ollama_vram()
        return

    passed_count = 0
    quarantined_count = 0

    try:
        for idx, kf in enumerate(pending_files, 1):
            print(f"[{idx}/{len(pending_files)}] Auditing: {kf.name[:45]}...", end=" ", flush=True)
            try:
                verdict, reason, raw = inspect_image(kf)
                
                if verdict == "FAIL":
                    quarantined_count += 1
                    dest = REJECTS_DIR / kf.name
                    shutil.move(kf, dest)
                    print(f"❌ MUTATION: {reason} -> Quarantined!")
                    status = "QUARANTINED"
                else:
                    passed_count += 1
                    print("✅ CLEAN")
                    status = "PASS"

                ledger[kf.name] = {
                    "verdict": verdict,
                    "reason": reason,
                    "status": status,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }

                with open(AUDIT_LEDGER_FILE, "w", encoding="utf-8") as f:
                    json.dump(ledger, f, indent=2)

            except Exception as e:
                print(f"⚠️ Error: {e}")

    finally:
        purge_ollama_vram()

    print("\n" + "=" * 80)
    print(f"🎉 Anatomy Audit Complete: {passed_count} Verified Clean | {quarantined_count} Mutants Quarantined")
    print(f"Remaining Clean Keepers in Vault: {len(list(KEEPERS_DIR.glob('*.png')))}")
    print("=" * 80)

if __name__ == "__main__":
    main()
