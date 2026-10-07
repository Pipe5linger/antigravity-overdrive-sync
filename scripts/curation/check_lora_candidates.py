from pathlib import Path

lora_dir = Path(r"D:\AI\Projects\ComfyUI\models\loras")

candidates = {
    "Anatomy_Sliders": [
        "zit_thickness.safetensors",
        "Z-Hip-Slider.safetensors",
        "Vespera_Body_Physique_v1_ComfyNative.safetensors",
        "z-image-turbo_hourglass-figure.safetensors",
        "ZIB_SkinnyVoluptousSlider_v5.1.safetensors"
    ],
    "Skin_Realism": [
        "fluxRealSkin-V2.safetensors",
        "skin texture Photorealistic style v4.5.safetensors",
        "OiledSkin_Zit_Turbo_V1.safetensors",
        "AntiPlastic_AnalogTexture_v1.safetensors",
        "ZiTD3tailedP0rtraits.safetensors",
        "REDZ15_DetailDaemonZ_lora_v1.1.safetensors"
    ],
    "Lighting_Atmosphere": [
        "Chiaroscuro zib v1.safetensors",
        "Neon_Noir_Atmospheric_Flux.safetensors",
        "DarkAtmospheric01_CE_ZIMG_AIT4k.safetensors",
        "50sNoirZ.safetensors",
        "Cinematic Film Color style v1.2.safetensors",
        "Low-key lighting Style v1.safetensors"
    ]
}

print(f"Checking LoRA candidates in: {lora_dir}")
valid_candidates = {}
for cat, files in candidates.items():
    print(f"\n=== {cat} ===")
    valid_candidates[cat] = []
    for f in files:
        p = lora_dir / f
        if p.is_file():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"  [OK] {f} ({size_mb:.1f} MB)")
            valid_candidates[cat].append(f)
        else:
            print(f"  [MISSING] {f}")

print("\nSummary of valid candidates per category:")
for cat, valid in valid_candidates.items():
    print(f"- {cat}: {len(valid)} available")
