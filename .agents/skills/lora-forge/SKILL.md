---
name: lora-forge
description: Comprehensive operational guide for LoRA dataset validation, aspect-ratio bucketing, configuration synthesis (.yaml/.toml for ai-toolkit, kohya_ss, OneTrainer), and training telemetry diagnostics.
---

# LORA-FORGE :: Diffusion Fine-Tuning & Training Skill

## 1. Scope & Ecosystem
This skill governs local low-rank adaptation (LoRA) and fine-tuning pipelines on the **NVIDIA GeForce RTX 4070 (12GB VRAM)** across the following toolkits:
* **`ai-toolkit`** (`d:\AI\Projects\ai-toolkit`): Primary engine for Flux.1 and SDXL diffusion model fine-tuning.
* **`kohya_ss`** (`d:\AI\Projects\kohya_ss`): Precision trainer for SDXL / SD 1.5 with GUI and headless CLI execution.
* **`OneTrainer`** (`d:\AI\Projects\OneTrainer-master`): Flexible, highly modular training engine with deep tensor control.
* **`ZIT_LoRA_Trainer`** (`d:\AI\Projects\ZIT_LoRA_Trainer`): Dedicated zero-iteration / fast-adaptation pipeline.

---

## 2. Dataset Hygiene & Pre-Flight Parity Rules

Before generating training configurations or launching a run, verify dataset integrity:

### A. 1:1 Pairing Verification
Every training image (`.png`, `.jpg`, `.jpeg`, `.webp`) must have an identical basename `.txt` caption file in the same directory:
```
dataset/
├── vespera_001.png
├── vespera_001.txt
├── vespera_002.png
└── vespera_002.txt
```
* **Orphan Rule**: Flag any image lacking a `.txt` or any `.txt` lacking a corresponding image.
* **Zero-Byte Rule**: Purge or populate any 0-byte `.txt` files.

### B. Caption Formatting Standards
* **Trigger Placement**: Place the activation token as the first token (e.g., `vespera, a woman with voluminous jet-black corkscrew curls...`).
* **Flux.1 Style**: Natural language descriptions, full sentences, rich semantic descriptors. Avoid pure tag soup.
* **SDXL / SD 1.5 Style**: Comma-separated tags, prioritized from dominant subject traits to background and lighting details.

### C. Resolution & Aspect-Ratio Buckets
Standardize images into target aspect-ratio buckets to avoid distortion during training:
* **1:1**: `1024x1024`
* **Portrait (3:4 / 9:16)**: `896x1152`, `832x1216`, `768x1344`
* **Landscape (4:3 / 16:9)**: `1152x896`, `1216x832`, `1344x768`

---

## 3. RTX 4070 12GB VRAM Constraints & Safety Presets

To avoid CUDA Out-of-Memory (OOM) errors on 12GB VRAM:
1. **Precision**: Always train in `bf16` or `fp8` (specifically `fp8_e4m3fn` for Flux.1 transformer / DiT).
2. **Gradient Checkpointing**: Mandatory (`gradient_checkpointing: true`).
3. **Text Encoders**: Freeze text encoders (CLIP-L and T5-XXL) when training Flux.1 on 12GB; offload T5 to CPU or quantize if fine-tuning text encoders is strictly needed.
4. **Attention Mechanism**: Enforce `sdpa` (PyTorch Scaled Dot Product Attention) or `xformers`.
5. **Batch Size**: Batch size = 1 with gradient accumulation steps (`gradient_accumulation_steps: 2` or `4`) to achieve effective batch size 2-4 without VRAM ballooning.

---

## 4. Configuration Synthesis Runbooks

### A. `ai-toolkit` Flux.1 LoRA Config (`config.yaml`)
```yaml
job: extension
config:
  name: "vespera_flux_lora"
  process:
    - type: 'sd_trainer'
      training_folder: "D:/AI/Outputs/lora_training/vespera_flux"
      device: cuda:0
      network:
        type: "lora"
        linear: 16
        linear_alpha: 16
      save:
        dtype: float16
        save_every: 250
        max_step_saves_to_keep: 4
      datasets:
        - folder_path: "D:/AI/Projects/vespera_dataset_v2"
          caption_ext: "txt"
          caption_dropout_rate: 0.05
          shuffle_tokens: false
          cache_latents_to_disk: true
          resolution: [512, 768, 1024]
      train:
        batch_size: 1
        steps: 2000
        gradient_accumulation_steps: 2
        train_unet: true
        train_text_encoder: false
        gradient_checkpointing: true
        noise_scheduler: "flowmatch"
        optimizer: "adamw8bit"
        lr: 1e-4
        ema_config:
          use_ema: false
        dtype: bf16
```

### B. `kohya_ss` SDXL LoRA Config (`dataset.toml`)
```toml
[general]
enable_bucket = true
resolution = 1024
min_bucket_reso = 512
max_bucket_reso = 1536
bucket_reso_steps = 64
bucket_no_upscale = false

[[datasets]]
[[datasets.subsets]]
image_dir = "D:/AI/Projects/vespera_dataset_v2"
num_repeats = 10
caption_extension = ".txt"
keep_tokens = 1
```

---

## 5. Loss Curve & Telemetry Diagnostics

When diagnosing a training run:
1. **Initial Burn-In (Steps 1–100)**: Loss starts high (~0.30–0.50 for flow-matching) and descends rapidly.
2. **Convergence Zone (Steps 500–1500)**: Loss oscillates stably between 0.08 and 0.14.
3. **Overfitting Symptoms**:
   * Loss drops below 0.04 with steep gradient collapse.
   * Test renders exhibit skin burn, oversaturation, or duplicated limbs.
4. **Underfitting Symptoms**:
   * Loss plateaus above 0.22 after step 800.
   * Model fails to respond to activation token. Solution: increase learning rate from `1e-4` to `2e-4` or increase repeats.
