---
name: telemetry-ops
description: Operational procedures for GPU VRAM monitoring on RTX 4070 12GB, PyTorch memory management, and ComfyUI generation queue inspection.
---

# Telemetry, VRAM Guard & ComfyUI Operations Guide

## 1. System Constraints
* **GPU**: NVIDIA GeForce RTX 4070 (12,282 MB VRAM).
* **VRAM Redline**: 10,500 MB (85%). Beyond this threshold, PyTorch out-of-memory allocations cause catastrophic task crashes.
* **ComfyUI Endpoint**: `http://127.0.0.1:8188`.

---

## 2. Tools & Commands

### `ulm_vram_guard(action='check'|'purge')`
* `action='check'`: Retrieves current total, used, and free GPU VRAM, along with GPU temperature and current utilization percentage.
* `action='purge'`: Executes `torch.cuda.empty_cache()` and garbage collection to immediately free unreferenced CUDA allocations.

### `ulm_comfy_status()`
* Connects to ComfyUI's REST API and returns:
  * Current execution status (idle vs processing prompt).
  * Remaining queue depth.
  * Recent generation errors and execution node history.

---

## 3. Standard Operating Procedures

1. **Pre-Generation VRAM Check**:
   Before initiating model compilation, large batch inference, or embedding re-indexing, execute `ulm_vram_guard(action='check')`. If used VRAM > 9,000 MB, issue `action='purge'` before proceeding.
2. **Post-Crash Recovery**:
   If ComfyUI or an Ollama worker hangs, check `ulm_comfy_status()`. If a queue is wedged, call `comfy_interrupt` or `comfy_clear_queue` via MCP tools to unblock the pipeline.
