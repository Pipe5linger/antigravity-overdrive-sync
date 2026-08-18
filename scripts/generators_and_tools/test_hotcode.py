#!/usr/bin/env python3
"""
Hotcode Directives Verification Test
Tests: persona_baseline.yaml modification -> DynamicPromptAssembler -> Modelfile.local output
"""

import sys
from pathlib import Path

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.assembler import DynamicPromptAssembler
from core.compiler import compile_and_bake

DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"
MODELFILE_PATH = PROJECT_ROOT / "Modelfile.local"

def run_test():
    # 1. Instantiate the Assembler
    assembler = DynamicPromptAssembler(workspace_root=PROJECT_ROOT)

    # 2. Hotcode a test directive into persona_baseline.yaml
    TEST_KEY = "terminal_focus_override"
    TEST_VALUE = "Refuse to indulge in unnecessary idle chatter when active terminal code refactoring is in progress."

    print(f"[*] Injecting directive '{TEST_KEY}' into persona_baseline.yaml...")
    success = assembler.inject_baseline_directive(TEST_KEY, TEST_VALUE)

    if not success:
        print("[-] Hotcode injection failed! Exiting test.")
        return False

    # 3. Trigger compiler pass
    print("\n[*] Running compiler pass...")
    compile_and_bake()

    # 4. Verify output in Modelfile.local
    print("\n[*] Inspecting Modelfile.local for injected directive...")
    if MODELFILE_PATH.exists():
        content = MODELFILE_PATH.read_text(encoding="utf-8")
        
        if TEST_VALUE in content:
            print("\n[SUCCESS] Hotcode Directive Verified in Modelfile.local!")
            print("-------------------------------------------------------------")
            # Print matching snippet context
            for line in content.splitlines():
                if TEST_KEY.upper() in line or TEST_VALUE in line:
                    print(f" Found Line: {line.strip()}")
            print("-------------------------------------------------------------")
            return True
        else:
            print("\n[FAILED] Injected directive was NOT found in Modelfile.local.")
            return False
    else:
        print("\n[-] Modelfile.local does not exist.")
        return False

if __name__ == "__main__":
    result = run_test()
    if not result:
        exit(1)