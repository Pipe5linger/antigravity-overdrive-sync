#!/usr/bin/env python3
"""
Antigravity Overdrive :: End-to-End Pipeline Smoke Test
Validates:
  1. Hotcode directive injection into persona_baseline.yaml
  2. Sequential execution of all dynamic sync injectors
  3. Verification that the injected directive exists across ALL 3 output targets:
     - Modelfile.local (Ollama Core)
     - .clinerules     (Cline IDE)
     - GEMINI.md       (Gemini Master Context)
"""

import sys
import time
from pathlib import Path

# Workspace Root Setup
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.assembler import DynamicPromptAssembler
from core.compiler import compile_and_bake
from injectors.cline_rules import ClineRulesInjector
from injectors.gemini_md import GeminiMdInjector

# Verification Targets
TARGET_FILES = {
    "Ollama Modelfile": PROJECT_ROOT / "Modelfile.local",
    "Cline Rules": PROJECT_ROOT / ".clinerules",
    "Gemini Directive": PROJECT_ROOT / "GEMINI.md",
}

# Unique directive payload for this test run
TEST_DIRECTIVE_KEY = "live_sync_verification_override"
TEST_DIRECTIVE_VAL = f"E2E Test Directive Generated At {time.strftime('%Y-%m-%d %H:%M:%S')}"


def run_e2e_test():
    print("================================================================================")
    print("        ANTIGRAVITY OVERDRIVE :: END-TO-END PIPELINE SMOKE TEST                  ")
    print("================================================================================")

    # --------------------------------------------------------------------------
    # STEP 1: Inject Test Directive into persona_baseline.yaml
    # --------------------------------------------------------------------------
    print("\n[Step 1/3] Injecting test hotcode directive into persona_baseline.yaml...")
    assembler = DynamicPromptAssembler(workspace_root=PROJECT_ROOT)
    injected = assembler.inject_baseline_directive(TEST_DIRECTIVE_KEY, TEST_DIRECTIVE_VAL)

    if not injected:
        print("[-] Critical Error: Failed to inject directive into YAML baseline.")
        return False

    print(f"[+] Directives updated in YAML. Injected string:\n    '{TEST_DIRECTIVE_VAL}'")

    # --------------------------------------------------------------------------
    # STEP 2: Execute All Target Injectors
    # --------------------------------------------------------------------------
    print("\n[Step 2/3] Triggering full multi-target sync pipeline...")

    # 2a. Compile Ollama Modelfile
    print("  -> Compiling Ollama Modelfile & baking Vespera...")
    compile_and_bake()

    # 2b. Sync Cline Rules
    print("  -> Injecting .clinerules...")
    ClineRulesInjector(workspace_root=PROJECT_ROOT).inject()

    # 2c. Sync Gemini MD
    print("  -> Injecting GEMINI.md...")
    GeminiMdInjector(workspace_root=PROJECT_ROOT).inject()

    # --------------------------------------------------------------------------
    # STEP 3: Verify Persona Propagation Across All Targets
    # --------------------------------------------------------------------------
    print("\n[Step 3/3] Inspecting output artifacts for target alignment...")
    print("────────────────────────────────────────────────────────────────────────────────")

    all_passed = True

    for label, filepath in TARGET_FILES.items():
        if not filepath.exists():
            print(f"[FAIL] {label:<18} -> File does not exist ({filepath.name})")
            all_passed = False
            continue

        content = filepath.read_text(encoding="utf-8")
        
        # Check if the injected text was compiled into the output file
        if TEST_DIRECTIVE_VAL in content:
            print(f"[PASS] {label:<18} -> Correctly received injected directive!")
        else:
            print(f"[FAIL] {label:<18} -> Directive MISSING from {filepath.name}")
            all_passed = False

    print("────────────────────────────────────────────────────────────────────────────────")

    if all_passed:
        print("\n[SUCCESS] Pipeline verified! Persona state propagated to ALL endpoints.")
    else:
        print("\n[FAILURE] One or more targets failed to receive the dynamic persona state.")

    return all_passed


if __name__ == "__main__":
    success = run_e2e_test()
    sys.exit(0 if success else 1)