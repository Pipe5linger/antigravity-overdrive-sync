#!/usr/bin/env python3
"""
Antigravity Overdrive :: ComfyUI FastMCP Server
Model Context Protocol (MCP) Server for ComfyUI generation & workflow orchestration.
Connects directly to local ComfyUI API endpoint (default: http://127.0.0.1:8188).

Provides native agentic tools for:
  - comfy_get_status: Checks queue status, running prompts, and system device stats.
  - comfy_list_models: Discovers installed checkpoints, LoRAs, VAEs, and upscalers.
  - comfy_list_object_info: Inspects available nodes, required input parameters, and widget types.
  - comfy_get_history: Inspects past executions, output images, and execution errors.
  - comfy_queue_prompt: Submits a complete workflow graph payload to be rendered.
  - comfy_interrupt: Immediately stops the currently executing generation.
  - comfy_clear_queue: Clears all pending executions from the queue.
  - comfy_free_memory: Frees cached models and executes PyTorch garbage collection in ComfyUI.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Enforce UTF-8 on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except AttributeError:
        pass

COMFY_HOST = os.getenv("COMFYUI_HOST", "127.0.0.1")
COMFY_PORT = int(os.getenv("COMFYUI_PORT", "8188"))
COMFY_BASE_URL = f"http://{COMFY_HOST}:{COMFY_PORT}"

# Initialize FastMCP Server
mcp = FastMCP(
    name="comfyui",
    instructions="ComfyUI Generation Pipeline, Workflow Orchestration & Hardware Telemetry Server"
)

def _http_request(endpoint: str, method: str = "GET", data: dict = None, timeout: float = 5.0):
    """Executes a JSON HTTP request against the ComfyUI REST API."""
    url = f"{COMFY_BASE_URL}{endpoint}"
    headers = {"User-Agent": "Antigravity-ComfyUI-MCP/1.0"}
    
    encoded_data = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        encoded_data = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "application/json" in content_type or raw.startswith(b"{") or raw.startswith(b"["):
                return json.loads(raw.decode("utf-8"))
            return raw.decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise ConnectionError(f"ComfyUI API unreachable at {url}: {e}")

@mcp.tool()
def comfy_get_status() -> str:
    """Checks the live operational status, queue length, and device hardware telemetry of ComfyUI.
    Use this before queuing workloads to verify that ComfyUI is online and not already saturated.
    """
    try:
        queue_data = _http_request("/queue")
        running = queue_data.get("queue_running", [])
        pending = queue_data.get("queue_pending", [])

        stats_text = ""
        try:
            sys_stats = _http_request("/system_stats")
            devices = sys_stats.get("devices", [])
            if devices:
                dev = devices[0]
                total = dev.get("vram_total", 0) / (1024 * 1024)
                free = dev.get("vram_free", 0) / (1024 * 1024)
                stats_text = f"\n- **GPU Device**: {dev.get('name', 'NVIDIA')} (Free VRAM: {free:,.0f} MB / {total:,.0f} MB)"
        except Exception:
            pass

        lines = [
            f"### 🎨 ComfyUI Status ({COMFY_BASE_URL}):",
            f"- **Status**: 🟢 ONLINE",
            f"- **Active Prompts Running**: {len(running)}",
            f"- **Queued Tasks Pending**: {len(pending)}"
        ]
        if stats_text:
            lines.append(stats_text)

        if running:
            lines.append("\n**Running Prompts:**")
            for item in running[:3]:
                lines.append(f"  - Prompt ID: `{item[1] if len(item) > 1 else 'Unknown'}`")

        if pending:
            lines.append("\n**Queued Prompts:**")
            for item in pending[:3]:
                lines.append(f"  - Prompt ID: `{item[1] if len(item) > 1 else 'Unknown'}`")

        return "\n".join(lines)
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE or unreachable at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error retrieving ComfyUI status: {e}"

@mcp.tool()
def comfy_list_models(model_type: str = "all") -> str:
    """Discovers available models, checkpoints, LoRAs, and VAEs installed in ComfyUI.
    
    Args:
        model_type: Filter by 'checkpoints', 'loras', 'vae', 'upscale_models', or 'all' (default).
    """
    try:
        # Query object_info for Loader nodes which list available files in their widget options
        info = _http_request("/object_info")
        results = []

        mapping = {
            "checkpoints": ("CheckpointLoaderSimple", 0),
            "loras": ("LoraLoader", 0),
            "vae": ("VAELoader", 0),
            "upscale_models": ("UpscaleModelLoader", 0),
        }

        target_types = mapping.keys() if model_type.lower() == "all" else [model_type.lower()]

        for m_type in target_types:
            if m_type in mapping:
                node_name, input_idx = mapping[m_type]
                node_spec = info.get(node_name, {})
                required = node_spec.get("input", {}).get("required", {})
                
                files = []
                for param_name, spec in required.items():
                    if isinstance(spec, list) and len(spec) > 0 and isinstance(spec[0], list):
                        files = spec[0]
                        break

                results.append(f"### 📦 {m_type.upper()} ({len(files)} installed):")
                if files:
                    for f in files[:15]:
                        results.append(f"  - `{f}`")
                    if len(files) > 15:
                        results.append(f"  *...and {len(files) - 15} more.*")
                else:
                    results.append("  *(None detected)*")
                results.append("")

        return "\n".join(results).strip()
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error listing models: {e}"

@mcp.tool()
def comfy_get_history(prompt_id: str = "", limit: int = 5) -> str:
    """Inspects recent ComfyUI execution history, output image filenames, and node execution status.

    Args:
        prompt_id: Optional specific prompt ID to inspect. If empty, returns the most recent executions.
        limit: Max number of history items to return (default 5).
    """
    try:
        endpoint = f"/history/{prompt_id}" if prompt_id else f"/history?max_items={limit}"
        history = _http_request(endpoint)
        if not history:
            return "No execution history found in ComfyUI."

        lines = ["### 📜 ComfyUI Execution History:"]
        for pid, data in list(history.items())[:limit]:
            status = data.get("status", {})
            completed = status.get("completed", False)
            status_str = "✅ Completed" if completed else "⚠️ Incomplete / Failed"
            
            outputs = data.get("outputs", {})
            image_files = []
            for node_id, node_out in outputs.items():
                if "images" in node_out:
                    for img in node_out["images"]:
                        image_files.append(f"{img.get('subfolder', '')}/{img.get('filename', '')}".strip("/"))

            lines.append(f"\n- **Prompt ID**: `{pid}` [{status_str}]")
            if image_files:
                lines.append(f"  - **Generated Images**: {', '.join([f'`{i}`' for i in image_files])}")
            if status.get("messages"):
                for m in status["messages"]:
                    if m[0] == "execution_error":
                        lines.append(f"  - ❌ **Execution Error**: {m[1].get('exception_message', '')}")

        return "\n".join(lines)
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error retrieving execution history: {e}"

@mcp.tool()
def comfy_queue_prompt(prompt_workflow: str, client_id: str = "antigravity") -> str:
    """Submits a complete ComfyUI node graph JSON payload to be queued and rendered.
    
    Args:
        prompt_workflow: A valid JSON string representing the complete ComfyUI API prompt graph:
                         e.g. {"prompt": {"3": {"class_type": "KSampler", "inputs": {...}}, ...}}
        client_id: Optional client session identifier.
    """
    try:
        try:
            workflow_dict = json.loads(prompt_workflow)
        except json.JSONDecodeError as err:
            return f"[-] Invalid JSON provided: {err}"

        # If payload doesn't wrap inside {"prompt": ...}, wrap it automatically
        if "prompt" not in workflow_dict:
            payload = {"prompt": workflow_dict, "client_id": client_id}
        else:
            payload = workflow_dict
            if "client_id" not in payload:
                payload["client_id"] = client_id

        res = _http_request("/prompt", method="POST", data=payload)
        prompt_id = res.get("prompt_id")
        queue_number = res.get("number")

        if prompt_id:
            return (
                f"✅ **Workflow Queued Successfully**:\n"
                f"- **Prompt ID**: `{prompt_id}`\n"
                f"- **Queue Position**: #{queue_number}\n"
                f"- Use `comfy_get_history(prompt_id='{prompt_id}')` to check for generated image outputs."
            )
        else:
            return f"[-] ComfyUI rejected queue submission: {res}"
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}. Start ComfyUI before queuing workflows."
    except Exception as e:
        return f"[-] Error queuing prompt: {e}"

@mcp.tool()
def comfy_interrupt() -> str:
    """Immediately interrupts and halts the currently active generation in ComfyUI."""
    try:
        _http_request("/interrupt", method="POST")
        return "🛑 **ComfyUI Execution Interrupted**: Active generation has been signaled to halt."
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error interrupting ComfyUI: {e}"

@mcp.tool()
def comfy_clear_queue() -> str:
    """Clears all pending prompt tasks waiting in the ComfyUI queue."""
    try:
        _http_request("/queue", method="POST", data={"clear": True})
        return "🧹 **ComfyUI Queue Cleared**: All pending prompt tasks have been purged."
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error clearing queue: {e}"

@mcp.tool()
def comfy_free_memory(unload_models: bool = True, free_memory: bool = True) -> str:
    """Frees cached model weights and runs PyTorch CUDA garbage collection inside ComfyUI.
    Call this when switching from large diffusion UNet checkpoints (Flux/SDXL) to save VRAM.

    Args:
        unload_models: If true, unloads cached neural model weights from GPU VRAM to system RAM.
        free_memory: If true, forces Python garbage collection and torch.cuda.empty_cache().
    """
    try:
        payload = {"unload_models": unload_models, "free_memory": free_memory}
        _http_request("/free", method="POST", data=payload)
        return "✅ **ComfyUI Memory Freed**: Cached models unloaded and CUDA VRAM cache purged inside ComfyUI."
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error freeing ComfyUI memory: {e}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
