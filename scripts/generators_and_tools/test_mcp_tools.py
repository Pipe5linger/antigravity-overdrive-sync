#!/usr/bin/env python3
"""
File    : test_mcp_tools.py
Purpose : Automated verification test for the 5 native ULM MCP tools.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.mcp_server import ulm_recall, ulm_pin_fact, ulm_get_playbook, ulm_check_taboo, ulm_hardware_status

def test_all_tools():
    print("[1] Testing ulm_hardware_status...")
    hw = ulm_hardware_status()
    assert "Workstation Hardware" in hw
    print("  -> Passed")

    print("[2] Testing ulm_check_taboo...")
    taboo = ulm_check_taboo("python test.py")
    assert "PASSED" in taboo or "TABOO" in taboo
    print("  -> Passed")

    print("[3] Testing ulm_recall...")
    rec = ulm_recall("sqlite", limit=2)
    assert "ULM Memory Recall" in rec or "No memories found" in rec
    print("  -> Passed")

    print("[4] Testing ulm_get_playbook...")
    pb = ulm_get_playbook("sync")
    assert "Playbook" in pb or "No procedural playbooks" in pb
    print("  -> Passed")

    print("[5] Testing ulm_pin_fact...")
    pin = ulm_pin_fact("Automated test golden fact verification", category="Testing", project_tag="test")
    assert "Successfully pinned" in pin
    print("  -> Passed")

    print("\n[SUCCESS] All ULM MCP tools verified functional!")

if __name__ == "__main__":
    test_all_tools()
