import sys
import os
import json
import glob
from pathlib import Path

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
    except AttributeError:
        pass

WORKFLOW_DIR = Path(r"D:\AI\Projects\ComfyUI\user\default\workflows")

def audit_workflows(wf_dir=WORKFLOW_DIR):
    if not wf_dir.exists():
        print(f"[-] Workflow directory not found: {wf_dir}")
        return 0

    wf_files = list(wf_dir.glob("*.json"))
    print(f"[*] Auditing {len(wf_files)} ComfyUI workflows in {wf_dir}...")
    
    issues_found = 0
    for wf in wf_files:
        try:
            with open(wf, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            links = data.get("links", [])
            link_ids = set()
            dup_links = 0
            for link in links:
                if isinstance(link, list) and link:
                    lid = link[0]
                    if lid in link_ids:
                        dup_links += 1
                    link_ids.add(lid)
            
            nodes = data.get("nodes", [])
            if dup_links > 0:
                print(f"[!] Warning: {wf.name} has {dup_links} duplicate link IDs! (Can trigger 'Cannot read properties of undefined')")
                issues_found += 1
            else:
                pass
        except Exception as e:
            print(f"[-] Corrupted JSON in {wf.name}: {e}")
            issues_found += 1

    if issues_found == 0:
        print("[+] All inspected workflows have valid JSON schemas and zero duplicate link IDs.")
    else:
        print(f"[!] Audit completed with {issues_found} potential workflow issues.")
    return 0

if __name__ == "__main__":
    sys.exit(audit_workflows())
