#!/usr/bin/env python3
"""
Antigravity Overdrive :: ComfyUI FastMCP Sovereign Generation Server
Model Context Protocol (MCP) Server for ComfyUI generation, prompt synthesis,
workflow orchestration, image recipe extraction, and hardware telemetry.
Connects directly to local ComfyUI API endpoint (default: http://127.0.0.1:8188).
"""

import os
import sys
import json
import time
import asyncio
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Any

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
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
DEFAULT_OUTPUT_DIRS = [
    Path(r"D:\AI\Antigravity outputs\generated_images"),
    Path(r"D:\AI\Outputs"),
    COMFY_DIR / "output"
]

# Physical Baseline Constants (from Sovereign GEMINI.md)
VESPERA_FULL_BIOMETRICS = (
    "vespera, hyper-realistic, 5'5\" woman late-30s of French-Levantine and Mediterranean heritage, "
    "pronounced hourglass figure, natural facial asymmetry, subtle asymmetrical half-smirk, "
    "sculpted facial structure, high cheekbones, elegant soft-tapered button nose, "
    "unblemished luminous warm olive skin retaining photorealistic micro-pores, fine skin texture, golden undertones, "
    "specular highlights on cheekbones and collarbones, deep hazel-green almond-shaped eyes, "
    "soft-smudged smoky black eyeliner, subtle lash shadow, full soft black satin lips, "
    "tiny beauty mark beside upper-left lip corner, voluminous jet-black 3B/3C spiral corkscrew curls "
    "cascading to mid-back with fine interwoven electric-indigo highlights, no bangs, framing face, "
    "athletic narrow waist, defined vertical navel, wide hips, full perfectly rounded gluteal contours, "
    "toned thighs, natural firm high-set D-cup bust, perfectly formed hands, relaxed confident poise"
)

VESPERA_BENCHMARK_TRIGGER = "vespera"

DEFAULT_NEGATIVE_PROMPT = (
    "text, watermark, logo, banner, blurry, deformed, bad anatomy, bad hands, missing fingers, "
    "extra fingers, cropped, low quality, artifact, duplicate, plastic skin, doll, cartoon, 3d render"
)

# Initialize FastMCP Server
mcp = FastMCP(
    name="comfyui",
    instructions="ComfyUI Sovereign Generation, Workflow Orchestration & Hardware Telemetry Server"
)

def _http_request(endpoint: str, method: str = "GET", data: dict = None, timeout: float = 5.0):
    """Executes a JSON HTTP request against the ComfyUI REST API."""
    url = f"{COMFY_BASE_URL}{endpoint}"
    headers = {"User-Agent": "Antigravity-ComfyUI-MCP/2.0"}
    
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

# ==============================================================================
# 1. CORE OPERATIONAL & TELEMETRY TOOLS
# ==============================================================================

@mcp.tool()
def comfy_get_status() -> str:
    """Checks the live operational status, queue length, and device hardware telemetry of ComfyUI."""
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
                node_name, _ = mapping[m_type]
                node_spec = info.get(node_name, {})
                required = node_spec.get("input", {}).get("required", {})
                
                files = []
                for _, spec in required.items():
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
    """Inspects recent ComfyUI execution history, output image filenames, and node execution status."""
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
            for _, node_out in outputs.items():
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
    """Submits a complete ComfyUI node graph JSON payload to be queued and rendered."""
    try:
        try:
            workflow_dict = json.loads(prompt_workflow)
        except json.JSONDecodeError as err:
            return f"[-] Invalid JSON provided: {err}"

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
                f"- Use `comfy_get_history(prompt_id='{prompt_id}')` or `comfy_await_generation` to monitor."
            )
        else:
            return f"[-] ComfyUI rejected queue submission: {res}"
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
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
        return f"[-] Error interrupting execution: {e}"

@mcp.tool()
def comfy_clear_queue() -> str:
    """Clears all pending executions from the ComfyUI queue."""
    try:
        _http_request("/queue", method="POST", data={"clear": True})
        return "🧹 **ComfyUI Queue Cleared**: All pending generation requests removed."
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error clearing queue: {e}"

@mcp.tool()
def comfy_free_memory(unload_models: bool = True, free_memory: bool = True) -> str:
    """Frees cached models and triggers PyTorch garbage collection inside ComfyUI."""
    try:
        payload = {"unload_models": unload_models, "free_memory": free_memory}
        _http_request("/free", method="POST", data=payload)
        return "⚡ **ComfyUI Memory Purged**: Cached models unloaded and PyTorch CUDA cache freed."
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error freeing ComfyUI memory: {e}"

# ==============================================================================
# 2. HIGH-LEVERAGE GENERATIVE & SYNTHESIS TOOLS
# ==============================================================================

@mcp.tool()
def comfy_synth_vespera_prompt(
    scene: str,
    wardrobe: str = "black silk satin tailored blazer and wide-leg trousers",
    mood: str = "sultry, mysterious, atmospheric Parisian noir",
    mode: str = "narrative",
    camera_shot: str = "cinematic medium shot, 85mm lens, f/1.8, bokeh"
) -> str:
    """Synthesizes a rule-compliant, Taboo-sanitized Vespera generation prompt.
    
    Args:
        scene: Description of setting, environment, and background details (e.g. 'rainy Paris street near the Seine').
        wardrobe: Clothing, fabrics, styling, or jewelry.
        mood: Lighting, emotional tone, and atmosphere.
        mode: 'narrative' (injects full hyper-realistic biometrics) or 'benchmark' (raw 'vespera' trigger only for LoRA testing).
        camera_shot: Cinematic composition and lens styling.
    """
    # 1. Base anchor
    if mode.lower() == "benchmark":
        subject = f"{VESPERA_BENCHMARK_TRIGGER}, raw aesthetic test"
    else:
        subject = VESPERA_FULL_BIOMETRICS

    # 2. Assemble positive prompt
    components = [
        subject,
        f"wearing {wardrobe.strip()}" if wardrobe else "",
        f"setting: {scene.strip()}" if scene else "",
        f"atmosphere: {mood.strip()}" if mood else "",
        f"composition: {camera_shot.strip()}" if camera_shot else "",
        "masterpiece, 8k resolution, authentic film grain, photorealistic specular highlights"
    ]
    positive_raw = ", ".join([c for c in components if c])

    # 3. Taboo Sanitization: Strip quotes, resolve duplicate commas
    sanitized_pos = positive_raw.replace('"', '').replace("'", '').replace("  ", " ").strip()
    while ", ," in sanitized_pos:
        sanitized_pos = sanitized_pos.replace(", ,", ",")

    sanitized_neg = DEFAULT_NEGATIVE_PROMPT

    return (
        f"### ✨ Synthesized Vespera Prompt ({mode.upper()} MODE):\n\n"
        f"**Positive Prompt:**\n```text\n{sanitized_pos}\n```\n\n"
        f"**Negative Prompt:**\n```text\n{sanitized_neg}\n```\n\n"
        f"*Ready for execution via `comfy_quick_render` or custom graph submission.*"
    )

@mcp.tool()
def comfy_quick_render(
    prompt: str,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    checkpoint: str = "",
    lora: str = "",
    lora_weight: float = 0.85,
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 6.0,
    sampler_name: str = "dpmpp_2m",
    scheduler: str = "karras",
    seed: int = -1
) -> str:
    """One-shot image generator: dynamically builds a complete standard txt2img graph and queues it in ComfyUI.
    
    Args:
        prompt: Positive generation prompt.
        negative_prompt: Negative generation prompt.
        checkpoint: Checkpoint filename. If blank, automatically picks the first available checkpoint from ComfyUI.
        lora: Optional LoRA filename (e.g. 'vespera_lora.safetensors').
        lora_weight: LoRA model and clip strength (default 0.85).
        width: Image width (default 1024).
        height: Image height (default 1024).
        steps: KSampler sampling steps (default 25).
        cfg: Classifier-Free Guidance scale (default 6.0).
        sampler_name: Sampler algorithm (e.g. 'euler', 'dpmpp_2m', 'dpmpp_sde').
        scheduler: Noise scheduler ('normal', 'karras', 'exponential', 'sgm_uniform').
        seed: Random seed. If -1, automatically generates a secure random 64-bit seed.
    """
    try:
        # Auto-discover checkpoint if not supplied
        if not checkpoint:
            info = _http_request("/object_info")
            ckpt_node = info.get("CheckpointLoaderSimple", {})
            ckpt_list = ckpt_node.get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            if not ckpt_list:
                return "[-] No checkpoints installed or detected in ComfyUI."
            checkpoint = ckpt_list[0]

        actual_seed = seed if seed != -1 else int(time.time() * 1000) % (2**31)

        # Build clean modular API graph
        workflow = {}

        # Node 1: Checkpoint Loader
        workflow["1"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint}
        }
        model_out = ["1", 0]
        clip_out = ["1", 1]
        vae_out = ["1", 2]

        # Node 2: Optional LoRA Loader
        if lora:
            workflow["2"] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": lora,
                    "strength_model": lora_weight,
                    "strength_clip": lora_weight,
                    "model": model_out,
                    "clip": clip_out
                }
            }
            model_out = ["2", 0]
            clip_out = ["2", 1]

        # Node 3: Positive CLIP Text Encode
        workflow["3"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": clip_out
            }
        }

        # Node 4: Negative CLIP Text Encode
        workflow["4"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": clip_out
            }
        }

        # Node 5: Empty Latent Image
        workflow["5"] = {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        }

        # Node 6: KSampler
        workflow["6"] = {
            "class_type": "KSampler",
            "inputs": {
                "seed": actual_seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": 1.0,
                "model": model_out,
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0]
            }
        }

        # Node 7: VAE Decode
        workflow["7"] = {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["6", 0],
                "vae": vae_out
            }
        }

        # Node 8: Save Image
        workflow["8"] = {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "Vespera_Sovereign",
                "images": ["7", 0]
            }
        }

        # Queue prompt
        payload = {"prompt": workflow, "client_id": "vespera_sovereign"}
        res = _http_request("/prompt", method="POST", data=payload)
        prompt_id = res.get("prompt_id")
        q_num = res.get("number")

        return (
            f"🚀 **Quick Render Queued Successfully**:\n"
            f"- **Prompt ID**: `{prompt_id}`\n"
            f"- **Queue Position**: #{q_num}\n"
            f"- **Checkpoint**: `{checkpoint}`\n"
            f"- **LoRA**: `{lora or 'None'}` (Weight: {lora_weight})\n"
            f"- **Resolution**: {width}x{height} | **Seed**: `{actual_seed}`\n"
            f"- **Sampler**: `{sampler_name}` / `{scheduler}` ({steps} steps, CFG {cfg})\n"
            f"- Track completion with `comfy_await_generation(prompt_id='{prompt_id}')`"
        )
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error executing quick render: {e}"

@mcp.tool()
def comfy_extract_image_recipe(image_path: str) -> str:
    """Reads embedded ComfyUI generation parameters, positive/negative prompts, seed, and workflow from any PNG file.
    
    Args:
        image_path: Absolute or relative path to a generated PNG image.
    """
    path = Path(image_path)
    if not path.is_file():
        # Check in default output directories if basename supplied
        for out_dir in DEFAULT_OUTPUT_DIRS:
            candidate = out_dir / image_path
            if candidate.is_file():
                path = candidate
                break

    if not path.is_file():
        return f"[-] File not found: `{image_path}`"

    try:
        from PIL import Image
        with Image.open(path) as img:
            info = img.info
            if not info:
                return f"[-] No metadata found in image `{path.name}`."

            prompt_data = info.get("prompt")
            workflow_data = info.get("workflow")

            if not prompt_data and not workflow_data:
                return f"[-] Image `{path.name}` does not contain ComfyUI metadata."

            lines = [f"### 🔍 Image Recipe: `{path.name}`", f"- **Location**: `{path}`"]

            if prompt_data:
                try:
                    p_json = json.loads(prompt_data)
                    # Extract positive and negative prompts
                    pos_prompts = []
                    neg_prompts = []
                    ckpts = []
                    loras = []
                    sampler_info = {}

                    for _, node in p_json.items():
                        c_type = node.get("class_type", "")
                        inputs = node.get("inputs", {})

                        if c_type == "CLIPTextEncode":
                            text = inputs.get("text", "")
                            # Heuristic: negative usually contains 'watermark' or 'ugly'
                            if any(w in text.lower() for w in ["watermark", "ugly", "deformed", "blurry", "low quality"]):
                                neg_prompts.append(text)
                            else:
                                pos_prompts.append(text)
                        elif c_type == "CheckpointLoaderSimple":
                            ckpts.append(inputs.get("ckpt_name", ""))
                        elif c_type == "LoraLoader":
                            loras.append(f"{inputs.get('lora_name')} (str: {inputs.get('strength_model', 1.0)})")
                        elif c_type == "KSampler":
                            sampler_info = {
                                "seed": inputs.get("seed"),
                                "steps": inputs.get("steps"),
                                "cfg": inputs.get("cfg"),
                                "sampler": inputs.get("sampler_name"),
                                "scheduler": inputs.get("scheduler")
                            }

                    if pos_prompts:
                        lines.append(f"\n**Positive Prompt:**\n```text\n{pos_prompts[0]}\n```")
                    if neg_prompts:
                        lines.append(f"\n**Negative Prompt:**\n```text\n{neg_prompts[0]}\n```")
                    if ckpts:
                        lines.append(f"- **Checkpoint**: `{ckpts[0]}`")
                    if loras:
                        lines.append(f"- **LoRAs**: {', '.join([f'`{l}`' for l in loras])}")
                    if sampler_info:
                        lines.append(
                            f"- **Sampler Settings**: {sampler_info.get('sampler')} / {sampler_info.get('scheduler')} "
                            f"| Steps: {sampler_info.get('steps')} | CFG: {sampler_info.get('cfg')} | Seed: `{sampler_info.get('seed')}`"
                        )
                except Exception as err:
                    lines.append(f"*(Could not parse prompt JSON: {err})*")

            return "\n".join(lines)
    except Exception as e:
        return f"[-] Error extracting image metadata: {e}"

@mcp.tool()
def comfy_get_latest_output(max_results: int = 5) -> str:
    """Discovers the most recently generated PNG outputs across standard output directories."""
    all_files = []
    for out_dir in DEFAULT_OUTPUT_DIRS:
        if out_dir.is_dir():
            try:
                for f in out_dir.glob("*.png"):
                    if f.is_file():
                        all_files.append((f.stat().st_mtime, f))
            except Exception:
                pass

    if not all_files:
        return f"[-] No generated PNG images found in {', '.join(str(d) for d in DEFAULT_OUTPUT_DIRS)}."

    all_files.sort(key=lambda x: x[0], reverse=True)
    recent = all_files[:max_results]

    lines = [f"### 🖼️ Latest Generated Assets ({len(recent)} found):"]
    for mtime, p in recent:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
        size_mb = p.stat().st_size / (1024 * 1024)
        lines.append(f"- **`{p.name}`** ({size_mb:.2f} MB - {ts})\n  `{p}`")

    return "\n".join(lines)

@mcp.tool()
def comfy_await_generation(prompt_id: str, timeout_seconds: int = 90) -> str:
    """Blocks and monitors ComfyUI execution until the specified prompt ID finishes, returning the resulting image path.
    
    Args:
        prompt_id: The prompt ID returned from comfy_queue_prompt or comfy_quick_render.
        timeout_seconds: Maximum seconds to wait before returning status (default 90s).
    """
    start_time = time.time()
    try:
        while time.time() - start_time < timeout_seconds:
            history = _http_request(f"/history/{prompt_id}")
            if history and prompt_id in history:
                data = history[prompt_id]
                status = data.get("status", {})
                completed = status.get("completed", False)
                
                if completed:
                    outputs = data.get("outputs", {})
                    image_files = []
                    for _, node_out in outputs.items():
                        if "images" in node_out:
                            for img in node_out["images"]:
                                sub = img.get("subfolder", "")
                                fname = img.get("filename", "")
                                for d in DEFAULT_OUTPUT_DIRS:
                                    candidate = d / sub / fname if sub else d / fname
                                    if candidate.is_file():
                                        image_files.append(str(candidate))
                                        break
                                else:
                                    image_files.append(fname)

                    duration = time.time() - start_time
                    img_summary = "\n".join([f"  - `{p}`" for p in image_files])
                    return (
                        f"✅ **Render Complete** ({duration:.1f}s):\n"
                        f"- **Prompt ID**: `{prompt_id}`\n"
                        f"- **Generated Images**:\n{img_summary}"
                    )
                
                # Check for execution error
                if status.get("messages"):
                    for m in status["messages"]:
                        if m[0] == "execution_error":
                            return f"❌ **ComfyUI Generation Failed**: {m[1].get('exception_message', 'Unknown error')}"

            time.sleep(2.0)

        return f"⏳ **Generation Timed Out**: Prompt `{prompt_id}` is still processing after {timeout_seconds}s."
    except ConnectionError:
        return f"⚪ ComfyUI is OFFLINE at {COMFY_BASE_URL}."
    except Exception as e:
        return f"[-] Error awaiting generation: {e}"

@mcp.tool()
def comfy_launch_server() -> str:
    """Launches local ComfyUI backend on port 8188 in the background if currently offline."""
    # 1. Check if already online
    try:
        _http_request("/queue", timeout=2.0)
        return f"🟢 ComfyUI is already running and accessible on {COMFY_BASE_URL}."
    except Exception:
        pass

    if not COMFY_DIR.is_dir():
        return f"[-] ComfyUI root directory not found at `{COMFY_DIR}`."

    python_exe = COMFY_DIR / "venv" / "Scripts" / "python.exe"
    if not python_exe.is_file():
        python_exe = Path(sys.executable)

    main_script = COMFY_DIR / "main.py"
    if not main_script.is_file():
        return f"[-] ComfyUI main.py not found at `{main_script}`."

    cmd = [
        str(python_exe),
        str(main_script),
        "--listen", "127.0.0.1",
        "--port", str(COMFY_PORT),
        "--auto-launch"
    ]

    try:
        # Launch detached background process on Windows
        subprocess.Popen(
            cmd,
            cwd=str(COMFY_DIR),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform.startswith("win") else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return f"🚀 **ComfyUI Starting**: Dispatched background launch on port {COMFY_PORT}. Wait ~10 seconds, then call `comfy_get_status()`."
    except Exception as e:
        return f"[-] Failed to launch ComfyUI process: {e}"

@mcp.tool()
def comfy_pin_golden_recipe(
    title: str,
    prompt: str,
    seed: int,
    checkpoint: str,
    lora: str = "",
    notes: str = ""
) -> str:
    """Pins an exceptional generation recipe directly to Universal Local Memory (ULM) as a permanent golden fact.
    
    Args:
        title: Short descriptive name (e.g. 'Parisian Rain Trenchcoat Portrait').
        prompt: The positive generation prompt that produced the golden image.
        seed: The winning generation seed.
        checkpoint: Checkpoint model name.
        lora: LoRA model name and weight.
        notes: Stylistic observations or recommended settings.
    """
    try:
        from core.database import ULMDatabase
        db_path = Path(__file__).resolve().parent.parent / "db" / "sync_state.db"
        if not db_path.is_file():
            return f"[-] ULM state database not found at `{db_path}`."

        db = ULMDatabase(str(db_path))
        recipe_text = (
            f"GOLDEN_RECIPE [{title}]: Checkpoint: {checkpoint} | LoRA: {lora or 'None'} | "
            f"Seed: {seed} | Notes: {notes} | Prompt: {prompt}"
        )
        fact_id = db.add_fact(recipe_text, category="aesthetic", confidence=1.0, project_tag="comfyui")

        return (
            f"📌 **Golden Recipe Pinned to ULM**:\n"
            f"- **Title**: {title}\n"
            f"- **Fact ID**: `{fact_id}`\n"
            f"- **Seed**: `{seed}`\n"
            f"- Recipe stored in `db/sync_state.db` under category `aesthetic` for future recall."
        )
    except Exception as e:
        return f"[-] Error pinning recipe to ULM: {e}"

_FACE_ANALYSIS_APP = None


def _get_face_app():
    global _FACE_ANALYSIS_APP
    if _FACE_ANALYSIS_APP is None:
        try:
            from insightface.app import FaceAnalysis
            app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=0, det_size=(640, 640))
            _FACE_ANALYSIS_APP = app
        except Exception as e:
            raise RuntimeError(f"Could not initialize InsightFace buffalo_l: {e}")
    return _FACE_ANALYSIS_APP

@mcp.tool()
def comfy_match_facial_parity(
    image_path: str = "",
    anchor_path: str = "",
    min_threshold: float = 0.42
) -> str:
    """Evaluates biometric facial parity / identity consistency between a generated image and canonical Vespera anchors.
    
    Args:
        image_path: Absolute or relative path to the generated image. If blank, automatically inspects the newest image.
        anchor_path: Optional path to the reference anchor face. Defaults to D:\\AI\\Projects\\ZIT_LoRA_Trainer\\anchor_face_crop.png.
        min_threshold: Cosine similarity threshold for a 'Pass' rating (default 0.42).
    """
    import cv2
    import numpy as np

    # 1. Resolve Target Image
    target_file = None
    if image_path:
        p = Path(image_path)
        if p.is_file():
            target_file = p
        else:
            for out_dir in DEFAULT_OUTPUT_DIRS:
                cand = out_dir / image_path
                if cand.is_file():
                    target_file = cand
                    break
    else:
        # Find latest PNG
        all_pngs = []
        for out_dir in DEFAULT_OUTPUT_DIRS:
            if out_dir.is_dir():
                all_pngs.extend([(f.stat().st_mtime, f) for f in out_dir.glob("*.png") if f.is_file()])
        if all_pngs:
            all_pngs.sort(key=lambda x: x[0], reverse=True)
            target_file = all_pngs[0][1]

    if not target_file or not target_file.is_file():
        return f"[-] Target image not found: `{image_path or 'No generated images detected'}`."

    # 2. Resolve Anchor
    default_anchor = Path(r"D:\AI\Projects\ZIT_LoRA_Trainer\anchor_face_crop.png")
    anchor_file = Path(anchor_path) if anchor_path and Path(anchor_path).is_file() else default_anchor

    if not anchor_file.is_file():
        return f"[-] Canonical anchor image not found at `{anchor_file}`."

    # 3. Extract Embeddings & Compute Similarity
    try:
        app = _get_face_app()

        # Target Face
        img_target = cv2.imread(str(target_file))
        if img_target is None:
            return f"[-] Failed to load image at `{target_file}` via OpenCV."

        faces_target = app.get(img_target)
        if not faces_target:
            return f"⚠️ **Facial Parity**: No face detected in `{target_file.name}`."

        # Sort by bounding box area to get primary face
        faces_target = sorted(faces_target, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)
        primary_face = faces_target[0]
        emb_target = primary_face.normed_embedding

        # Anchor Face
        img_anchor = cv2.imread(str(anchor_file))
        faces_anchor = app.get(img_anchor)
        if not faces_anchor:
            return f"[-] No face detected in canonical anchor `{anchor_file.name}`."

        emb_anchor = sorted(faces_anchor, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)[0].normed_embedding

        # Cosine similarity
        score = float(np.dot(emb_target, emb_anchor))

        # Classification
        if score >= 0.52:
            status = "🌟 GOLDEN PARITY (Near Clone / Flawless Identity Lock)"
            recommendation = "Eligible for Master LoRA dataset and Golden Recipe pinning."
        elif score >= min_threshold:
            status = "✅ PASS (High Parity / Authentic Vespera Match)"
            recommendation = "Solid identity retention. Ready for narrative outputs."
        elif score >= 0.35:
            status = "⚠️ SOFT DRIFT (Recognizable Likeness with Stylistic Shift)"
            recommendation = "Likeness diluted by lighting, camera angle, or low LoRA weight."
        else:
            status = "❌ FAIL (Identity Hallucination / Checkpoint Drift)"
            recommendation = "Face does not match canonical biometrics. Increase LoRA weight or adjust prompt."

        bbox = [int(v) for v in primary_face.bbox]
        det_score = float(primary_face.det_score)

        return (
            f"### 🧬 Facial Parity Analysis:\n"
            f"- **Target Asset**: `{target_file.name}`\n"
            f"- **Anchor Reference**: `{anchor_file.name}`\n"
            f"- **Biometric Parity Score**: **`{score:.4f}`** (Threshold: `{min_threshold}`)\n"
            f"- **Verdict**: {status}\n"
            f"- **Face Detection Confidence**: `{det_score:.2%}` | **BBox**: `{bbox}`\n"
            f"- **Guidance**: {recommendation}"
        )
    except Exception as e:
        return f"[-] Error computing facial parity: {e}"

if __name__ == "__main__":
    mcp.run()

