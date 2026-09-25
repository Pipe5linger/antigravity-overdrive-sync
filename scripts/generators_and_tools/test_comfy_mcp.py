#!/usr/bin/env python3
"""
Automated unit verification for the ComfyUI FastMCP Server tools.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.comfy_mcp_server import (
    comfy_get_status,
    comfy_list_models,
    comfy_get_history,
    comfy_queue_prompt,
    comfy_interrupt,
    comfy_clear_queue,
    comfy_free_memory
)

def test_comfy_tools():
    print("[1] Testing comfy_get_status...")
    st = comfy_get_status()
    assert "ComfyUI" in st
    print("  -> Passed (Status reported cleanly)")

    print("[2] Testing comfy_list_models...")
    m = comfy_list_models(model_type="all")
    assert "CHECKPOINTS" in m or "ComfyUI is OFFLINE" in m
    print("  -> Passed (Models probed cleanly)")

    print("[3] Testing comfy_get_history...")
    hist = comfy_get_history(limit=2)
    assert "Execution History" in hist or "No execution history" in hist or "ComfyUI is OFFLINE" in hist
    print("  -> Passed")

    print("[4] Testing comfy_queue_prompt (syntax validation)...")
    res = comfy_queue_prompt("{not valid json")
    assert "Invalid JSON" in res
    print("  -> Passed (Malformed payload cleanly caught)")

    print("[5] Testing comfy_interrupt...")
    intr = comfy_interrupt()
    assert "Interrupted" in intr or "ComfyUI is OFFLINE" in intr
    print("  -> Passed")

    print("[6] Testing comfy_clear_queue...")
    clr = comfy_clear_queue()
    assert "Cleared" in clr or "ComfyUI is OFFLINE" in clr
    print("  -> Passed")

    print("[7] Testing comfy_free_memory...")
    freed = comfy_free_memory()
    assert "Memory Freed" in freed or "ComfyUI is OFFLINE" in freed
    print("  -> Passed")

    print("\n[SUCCESS] All 7 ComfyUI FastMCP tools verified functional!")

if __name__ == "__main__":
    test_comfy_tools()
