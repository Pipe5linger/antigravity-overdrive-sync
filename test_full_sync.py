#!/usr/bin/env python3
"""
Antigravity Workspace Unified Sync Verification Suite
Executes sequentially across all sync targets:
  1. Modelfile.local (Ollama Core / compiler.py)
  2. .clinerules     (Cline IDE Injector / cline_rules.py)
  3. GEMINI.md       (Gemini Master Injector / gemini_md.py)
"""

import sys
import time
from pathlib import Path

# Workspace Root Setup
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import module targets
try:
    from core.compiler import compile_and_bake
    from injectors.cline_rules import ClineRulesInjector
    from injectors.gemini_md import GeminiMdInjector
except ImportError as e:
    print(f"[-] Critical Import Error: {e}")
    sys.exit(1)

# Target File Definitions
TARGETS = {
    "Ollama Modelfile": PROJECT_ROOT / "Modelfile.local",
    "Cline Rules": PROJECT_ROOT / ".clinerules",
    "Gemini Directive": PROJECT_ROOT / "GEMINI.md",
}

def run_unified_sync():
    print("================================================================================")
    print("         ANTIGRAVITY OVERDRIVE :: UNIFIED MULTI-TARGET SYNC SUITE               ")
    print("================================================================================\n")
    
    start_time = time.time()
    results = {}

    # --------------------------------------------------------------------------
    # STEP 1: Compile & Bake Ollama Modelfile
    # --------------------------------------------------------------------------
    print("[1/3] Executing core/compiler.py (Ollama Modelfile target)...")
    try:
        compile_and_bake()
        results["Ollama Modelfile"] = True
    except Exception as e:
        print(f"[-] Compiler failed: {e}")
        results["Ollama Modelfile"] = False

    print("\n--------------------------------------------------------------------------------")

    # --------------------------------------------------------------------------
    # STEP 2: Inject Cline IDE Rules
    # --------------------------------------------------------------------------
    print("[2/3] Executing injectors/cline_rules.py (.clinerules target)...")
    try:
        cline_injector = ClineRulesInjector(workspace_root=PROJECT_ROOT)
        cline_success = cline_injector.inject()
        results["Cline Rules"] = cline_success
    except Exception as e:
        print(f"[-] Cline Rules Injector failed: {e}")
        results["Cline Rules"] = False

    print("\n--------------------------------------------------------------------------------")

    # --------------------------------------------------------------------------
    # STEP 3: Inject Gemini Master Directive
    # --------------------------------------------------------------------------
    print("[3/3] Executing injectors/gemini_md.py (GEMINI.md target)...")
    try:
        gemini_injector = GeminiMdInjector(workspace_root=PROJECT_ROOT)
        gemini_success = gemini_injector.inject()
        results["Gemini Directive"] = gemini_success
    except Exception as e:
        print(f"[-] Gemini MD Injector failed: {e}")
        results["Gemini Directive"] = False

    # --------------------------------------------------------------------------
    # POST-RUN VERIFICATION & REPORTING
    # --------------------------------------------------------------------------
    elapsed = time.time() - start_time
    print("\n================================================================================")
    print("                         TARGET VERIFICATION AUDIT                              ")
    print("================================================================================\n")

    all_passed = True
    for label, target_path in TARGETS.items():
        execution_ok = results.get(label, False)
        exists = target_path.exists()
        size_bytes = target_path.stat().st_size if exists else 0
        
        status = "[PASS]" if (execution_ok and exists and size_bytes > 0) else "[FAIL]"
        if status == "[FAIL]":
            all_passed = False
            
        print(f"{status} {label:<18} -> {target_path.name} ({size_bytes:,} bytes)")

    print(f"\n[*] Suite finished in {elapsed:.2f}s")
    
    if all_passed:
        print("\n[SUCCESS] All synchronization targets successfully verified and aligned!")
    else:
        print("\n[WARNING] One or more sync targets failed verification. Review logs above.")

    return all_passed

if __name__ == "__main__":
    success = run_unified_sync()
    sys.exit(0 if success else 1)