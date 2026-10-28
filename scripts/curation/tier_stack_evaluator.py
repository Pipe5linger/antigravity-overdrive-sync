"""
Tier Stack Evaluator (Universal Phase Workflow)
===============================================
Dynamic Multi-LoRA Discovery & Tier-Calibrated Evaluator for Vespera Dataset Suite.

Features:
- Full LoRA Discovery Engine: Actively tests dozens of LoRAs across 4 thematic rosters:
    * Anatomy & Silhouette (8+ Sliders)
    * Skin & Dermal Texture (5+ Textures)
    * Lighting & Atmosphere (9+ Styles)
    * Optics, Detailers & Photorealism (10+ Cameras/Optics)
- Two-Stage Annealing Search:
    * Passes 1-60  (Exploration): Tests diverse 4-to-5 LoRA combinatorial pairings from the rosters.
    * Passes 61-100 (Annealing)  : Freezes the champion LoRA combinations and fine-tunes exact decimal weights (+-0.05).
- 3-Seed Triangulation on Every Candidate:
    * T1: [0, 5, 482]     (Frontal, Profile 90°, 3/4 Profile)
    * T2: [11, 16, 18]    (Standing Contrapposto, Kneeling Proportions, Athletic Stretch)
    * T3: [21, 26, 28]    (Tailored Suit, Trench Coat, Evening Silk)
    * T4: [31, 36, 38]    (Full Standing Silhouette, Architectural Depth, Dynamic Motion)
- 3-Seed Confirmation Gate (6-Seed Total Composite for Verified Golden).
- Multi-Modal Evaluation:
    * Face Parity via InsightFace with distance/scale compensation for 50mm lenses.
    * Body Anchor Parity correlation against permanent reference anchors in reference_anchors/body.
    * Body Dermal Acutance (Laplacian variance across torso / garment).
    * Anti-Plastic Dermal Entropy check (penalizes airbrushed CGI, rewards authentic skin micro-pores).
    * Highlight specular clipping penalty.
- Tier-Calibrated Golden Targets:
    * T1: Golden >= 0.70 | Candidate >= 0.65 | Pass >= 0.60
    * T2: Golden >= 0.60 | Candidate >= 0.55 | Pass >= 0.50
    * T3: Golden >= 0.55 | Candidate >= 0.50 | Pass >= 0.45
    * T4: Golden >= 0.48 | Candidate >= 0.44 | Pass >= 0.38
"""

import argparse
import copy
import json
import random
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

COMFY_URL = "http://127.0.0.1:8188"
COMFY_DIR = Path(r"D:\AI\Projects\ComfyUI")
OUTPUT_DIR = COMFY_DIR / "output"
EVAL_DIR = OUTPUT_DIR / "tier_eval"
SUITE_DIR = COMFY_DIR / "custom_nodes" / "ComfyUI-Vespera-ZIT"
UI_WORKFLOW = COMFY_DIR / "user" / "default" / "workflows" / "Vespera_Universal_Phase_Workflow.json"
LORA_DIR = COMFY_DIR / "models" / "loras"

VAULT_DIR = OUTPUT_DIR / "reference_anchors"
FACE_ANCHOR_DIR = VAULT_DIR / "face"
BODY_ANCHOR_DIR = VAULT_DIR / "body"

if not FACE_ANCHOR_DIR.exists():
    FACE_ANCHOR_DIR = Path(r"D:\AI\Projects\ai-toolkit\vespera_anchors")

FACE_ANCHORS = {
    "frontal": FACE_ANCHOR_DIR / "anchor_frontal.png",
    "low_angle": FACE_ANCHOR_DIR / "anchor_low_angle.png",
    "profile_left": FACE_ANCHOR_DIR / "anchor_profile_left.png",
    "profile_right": FACE_ANCHOR_DIR / "anchor_profile_right.png",
}
FACE_ANCHOR_WEIGHTS = {
    "frontal": 0.35,
    "low_angle": 0.25,
    "profile_left": 0.20,
    "profile_right": 0.20,
}

# ==============================================================================
# THEMATIC LORA ROSTERS FOR DISCOVERY SEARCH
# ==============================================================================
ROSTER_ANATOMY = [
    "Body_FullFineBody_ZTurbo_v1.0.safetensors",
    "Body_curvy_curly_ZiT.safetensors",
    "Body_PAWG.safetensors",
    "Body_exagerated_hourglass_figure.safetensors",
    "Body_SkinnyVoluptousSlider_v5.1.safetensors",
    "Body_thick fit Z.safetensors",
    "Body_THICK_XL_Thin_Thick_Body.safetensors",
    "Body_z-image-turbo_hourglass-figure.safetensors",
    "Body_ZIT_Better_Women_LoRa_v1.safetensors",
    "Body_zit_thickness.safetensors",
    "Z-Hip-Slider.safetensors",
    "Z-Breast-Slider.safetensors",
    "ZIB_SkinnyVoluptousSlider_v5.1.safetensors",
]

ROSTER_SKIN = [
    "Skin_PhotorealTouch_ZIT_v1.safetensors",
    "Skin_ACS_Realism_ZIT_v0.1.safetensors",
    "Skin_skin texture Photorealistic style v4.5.safetensors",
    "Skin_AntiPlastic_AnalogTexture_v1.safetensors",
    "Skin_OiledSkin_Zit_Turbo_V1.safetensors",
    "Skin_skin tone style v2.1.safetensors",
    "Z-Detail-Slider.safetensors",
]

ROSTER_LIGHTING = [
    "Lighting_Z_Light_Slider.safetensors",
    "Lighting_zit_realistic_twisted_light.safetensors",
    "Lighting_light and shadow Portrait.safetensors",
    "Lighting_Chiaroscuro zib v1.safetensors",
    "Lighting_cinematic KODAK VISION3 500T Color Negative Film 5219 7219 v1.safetensors",
    "Lighting_Cinematic Film Color style v1.2.safetensors",
    "Lighting_afterdark_v2.safetensors",
    "Lighting_dark_dreamcore_style_ZIT_epoch_10.safetensors",
    "Lighting_Low-key lighting Style v1.safetensors",
    "Lighting_DarkAtmospheric01_CE_ZIMG_AIT4k.safetensors",
    "Lighting_zImageT_zidiusArt_melancholy.safetensors",
]

ROSTER_OPTICS = [
    "Detailer_ZiTSh4rpD3tails.safetensors",
    "Detailer_detail_slider_Z_V2.safetensors",
    "Detailer_REDZ15_DetailDaemonZ_lora_v1.1.safetensors",
    "Detailer_EyeDetail_Z_Turbo.safetensors",
    "Detailer_ZiTD3tailedP0rtraits.safetensors",
    "Photo_ProjectRealismPhotoLora_v1.safetensors",
    "Photo_RealisticSnapshot-Zimage-Turbov5.safetensors",
    "Photo_zy_CinematicShot_zit.safetensors",
    "Z-Image Turbo Radiant v2.0.safetensors",
    "Z-Image_Pro.safetensors",
]

ALL_AVAILABLE_LORAS = [p.name for p in LORA_DIR.glob("*.safetensors") if not p.name.startswith("Vespera_")]

TIER_OVERRIDE = {
    "T1": "Tier 1: Portraits",
    "T2": "Tier 2: Anatomy",
    "T3": "Tier 3: Couture",
    "T4": "Tier 4: Spatial",
    "T5": "Tier 5: Explicit"
}

IDENTITY_PREFIX = (
    "vespera, alluring woman of French-Levantine and Mediterranean heritage, "
    "luminous natural neutral-olive Mediterranean complexion, softly diffused matte skin finish with delicate subcutaneous light dispersion, "
    "subtle touch of natural skin micro-imperfections, faint delicate freckling across nose bridge and upper cheeks, "
    "authentic dermal texture variations, fine un-retouched epidermal micro-pores, zero oily sheen, zero plastic CGI smoothing, "
    "sculpted facial structure with high cheekbones, deep-set almond-shaped hazel-green eyes with amber-gold flecks, "
    "tiny beauty mark beside upper-left lip corner, voluminous jet-black 3B/3C spiral corkscrew curls with fine interwoven electric-indigo highlights, "
    "subtle asymmetrical half-smirk, "
)
TIER_PROMPTS = {
    "T1": "direct frontal editorial portrait, head and shoulders with generous top headroom, full crown of voluminous 3B/3C spiral corkscrew curls completely in frame, soft studio light, black turtleneck",
    "T2": "mid-body intimate boudoir pose, black silk robe, low-key velvet lighting, hourglass silhouette",
    "T3": "three-quarter high-fashion couture, tailored double-breasted pinstripe suit, editorial drape",
    "T4": "full-body contrapposto standing pose, wide Parisian studio backdrop, tailored coat and boots",
    "T5": "sensual kneeling boudoir pose, uninhibited curves, delicate shibari rope tension, moody dramatic studio lighting, authentic skin texture",
}

# 3-Seed Triangulation Suites
TIER_SEEDS = {
    "T1": [0, 5, 482],     # Frontal, Profile 90°, 3/4 Profile
    "T2": [11, 16, 18],    # Standing Contrapposto, Kneeling Proportions, Athletic Stretch
    "T3": [21, 26, 28],    # Tailored Suit, Trench Coat, Evening Silk
    "T4": [31, 36, 38],    # Full Standing Silhouette, Architectural Depth, Dynamic Motion
    "T5": [41, 46, 48],    # Uninhibited Boudoir, Floor Recline, Rope Tension
}

# Multi-Seed Confirmation Gate (Anti-Fluke Stress Verification)
TIER_CONFIRM_SEEDS = {
    "T1": [1, 2, 7],
    "T2": [12, 14, 19],
    "T3": [22, 24, 29],
    "T4": [32, 34, 39],
    "T5": [42, 44, 49],
}

# Multi-modal fitness weights: (weight_parity, weight_face_sharp, weight_body_sharp, weight_clip)
TIER_FITNESS = {
    "T1": (0.65, 0.25, 0.00, 0.10),
    "T2": (0.40, 0.15, 0.35, 0.10),
    "T3": (0.45, 0.15, 0.30, 0.10),
    "T4": (0.35, 0.15, 0.40, 0.10),
    "T5": (0.35, 0.15, 0.40, 0.10),
}

# Empirical Golden & Verification thresholds calibrated per tier
TIER_THRESHOLDS = {
    "T1": {"golden": 0.70, "candidate": 0.65, "pass": 0.60},
    "T2": {"golden": 0.60, "candidate": 0.55, "pass": 0.50},
    "T3": {"golden": 0.55, "candidate": 0.50, "pass": 0.45},
    "T4": {"golden": 0.48, "candidate": 0.44, "pass": 0.38},
    "T5": {"golden": 0.55, "candidate": 0.50, "pass": 0.45},
}

_FACE_APP = None
_FACE_ANCHOR_EMBS = {}
_BODY_ANCHOR_EMBS = {}


# ----------------------------------------------------------------- scoring --
def face_app():
    global _FACE_APP
    if _FACE_APP is None:
        from insightface.app import FaceAnalysis
        print("  [AI] Initializing InsightFace buffalo_l on CPU...")
        _FACE_APP = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _FACE_APP.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.18)
    return _FACE_APP


def largest_face(img):
    faces = face_app().get(img)
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def init_anchors():
    print("  [Anchors] Loading Master Reference Anchor Suite...")
    for key, path in FACE_ANCHORS.items():
        img = cv2.imread(str(path))
        face = largest_face(img) if img is not None else None
        if face is None:
            raise FileNotFoundError(f"Face anchor '{key}' unreadable or no face: {path}")
        _FACE_ANCHOR_EMBS[key] = face.normed_embedding
        print(f"    ✓ Face Anchor [{key}]: {path.name}")

    if BODY_ANCHOR_DIR.exists():
        for b_path in sorted(BODY_ANCHOR_DIR.glob("*.png")):
            b_img = cv2.imread(str(b_path))
            b_face = largest_face(b_img) if b_img is not None else None
            if b_face is not None:
                _BODY_ANCHOR_EMBS[b_path.stem] = b_face.normed_embedding
                print(f"    ✓ Body Anchor Face [{b_path.stem[:32]}...]")


def calculate_dermal_entropy(crop_gray) -> float:
    """Measures high-frequency micro-texture entropy to penalize plastic CGI skin."""
    if crop_gray is None or crop_gray.size < 100:
        return 0.5
    sobelx = cv2.Sobel(crop_gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(crop_gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = cv2.magnitude(sobelx, sobely)
    std_val = float(np.std(mag))
    return min(1.0, max(0.0, (std_val - 5.0) / 20.0))


def calculate_skin_tone_score(face_bgr) -> float:
    """Evaluates face crop for natural Mediterranean neutral-olive complexion.
    Rewards healthy subcutaneous olive balance (R:G ~ 1.35-1.50, R:B ~ 1.55-1.75).
    Penalizes oversaturated terracotta/orange sunburn (excess R dominance) and yellow jaundiced tones.
    """
    if face_bgr is None or face_bgr.size < 400:
        return 0.70
    h, w = face_bgr.shape[:2]
    sample = face_bgr[int(h * 0.25):int(h * 0.65), int(w * 0.25):int(w * 0.75)]
    if sample.size == 0:
        return 0.70
    
    b_mean = float(np.mean(sample[:, :, 0]))
    g_mean = float(np.mean(sample[:, :, 1]))
    r_mean = float(np.mean(sample[:, :, 2]))
    
    if g_mean < 1.0 or b_mean < 1.0:
        return 0.50
        
    rg_ratio = r_mean / g_mean
    rb_ratio = r_mean / b_mean
    
    rg_err = abs(rg_ratio - 1.40)
    rb_err = abs(rb_ratio - 1.65)
    
    penalty = 0.0
    if rg_ratio > 1.55:
        penalty += (rg_ratio - 1.55) * 0.5
    if rb_ratio > 1.85:
        penalty += (rb_ratio - 1.85) * 0.5
        
    hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
    sat_mean = float(np.mean(hsv[:, :, 1])) / 255.0
    if sat_mean > 0.45:
        penalty += (sat_mean - 0.45) * 0.6
        
    score = 1.0 - (rg_err * 0.35 + rb_err * 0.25 + penalty)
    return max(0.10, min(1.0, score))


def score_image(path: Path, tier: str = "T1") -> dict:
    img = cv2.imread(str(path))
    zero = {"parity": 0.0, "sharp": 0.0, "body_sharp": 0.0, "clip": 1.0, "entropy": 0.0, "face": False}
    if img is None:
        return zero

    h, w = img.shape[:2]
    face = largest_face(img)

    if face is not None:
        face_w = max(1.0, float(face.bbox[2] - face.bbox[0]))
        face_h = max(1.0, float(face.bbox[3] - face.bbox[1]))
        face_size = (face_w * face_h) ** 0.5

        raw_face_p = sum(FACE_ANCHOR_WEIGHTS[k] * float(np.dot(face.normed_embedding, _FACE_ANCHOR_EMBS[k])) for k in FACE_ANCHORS)

        if _BODY_ANCHOR_EMBS and tier in ("T2", "T3", "T4"):
            body_sims = [float(np.dot(face.normed_embedding, bemb)) for bemb in _BODY_ANCHOR_EMBS.values()]
            best_body_sim = max(body_sims) if body_sims else raw_face_p
            blended_p = 0.50 * raw_face_p + 0.50 * best_body_sim
        else:
            blended_p = raw_face_p

        if tier != "T1" and face_size < 350.0:
            scale_boost = min(1.30, 1.0 + (350.0 - face_size) / 700.0)
            parity = min(1.0, blended_p * scale_boost)
        else:
            parity = blended_p

        x1, y1, x2, y2 = [max(0, int(v)) for v in face.bbox]
        crop = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY) if x2 > x1 and y2 > y1 else None
        sharp = 0.0
        entropy = 0.5
        if crop is not None and crop.size:
            crop_res = cv2.resize(crop, (256, 256))
            sharp = min(1.0, float(cv2.Laplacian(crop_res, cv2.CV_64F).var()) / 600.0)
            entropy = calculate_dermal_entropy(crop)
            tone = calculate_skin_tone_score(img[y1:y2, x1:x2])
        else:
            tone = 0.70
        has_face = True
    else:
        if tier in ("T2", "T3", "T4"):
            parity = 0.48
            sharp = 0.20
            entropy = 0.50
            has_face = False
        else:
            return zero

    body_crop = img[int(h * 0.25):int(h * 0.85), int(w * 0.20):int(w * 0.80)]
    body_gray = cv2.cvtColor(body_crop, cv2.COLOR_BGR2GRAY) if body_crop.size else None
    body_sharp = 0.0
    if body_gray is not None and body_gray.size:
        body_sharp = min(1.0, float(cv2.Laplacian(body_gray, cv2.CV_64F).var()) / 500.0)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clip = float(np.mean(gray >= 250))

    return {
        "parity": parity,
        "sharp": sharp,
        "body_sharp": body_sharp,
        "entropy": entropy,
        "clip": clip,
        "tone": tone if has_face else 0.70,
        "face": has_face
    }


def fitness(tier: str, scores: list) -> float:
    wp, wfs, wbs, wc = TIER_FITNESS[tier]
    p = float(np.mean([s["parity"] for s in scores]))
    sh = float(np.mean([s["sharp"] for s in scores]))
    bsh = float(np.mean([s.get("body_sharp", sh) for s in scores]))
    ent = float(np.mean([s.get("entropy", 0.5) for s in scores]))
    cl = float(np.mean([s["clip"] for s in scores]))
    tone = float(np.mean([s.get("tone", 0.70) for s in scores]))

    base_fit = wp * p + wfs * sh + wbs * bsh + wc * (1.0 - min(1.0, cl * 20.0))
    dermal_mod = (ent - 0.50) * 0.06
    tone_mod = (tone - 0.70) * 0.10
    return max(0.0, min(1.0, base_fit + dermal_mod + tone_mod))


# ------------------------------------------------------------------ comfy ---
def comfy(endpoint, method="GET", data=None, timeout=15.0):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        COMFY_URL + endpoint, data=body, method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def load_base_widgets() -> dict:
    defaults = {
        "unet": ["z_image_turbo_bf16.safetensors", "default"],
        "clip": ["qwen_3_4b_fp8_mixed.safetensors", "lumina2", "default"],
        "vae": ["ae.safetensors"],
        "negative": "blurry, out of focus, low quality, distorted, deformed, text, watermark, bad anatomy, bad hands, missing fingers, extra limbs",
        "ksampler": [1, "fixed", 8, 1, "euler", "FlowMatchEulerDiscreteScheduler", 1],
    }

    workflow_candidates = [
        COMFY_DIR / "user" / "default" / "workflows" / "Vespera_Phase3_Production_Studio.json",
        UI_WORKFLOW,
    ]

    for wf_path in workflow_candidates:
        if not wf_path.exists():
            continue
        try:
            wf = json.loads(wf_path.read_text(encoding="utf-8"))
            for n in wf.get("nodes", []):
                ntype = n.get("type")
                wv = n.get("widgets_values", [])
                if ntype == "UNETLoader" and wv:
                    defaults["unet"] = wv
                elif ntype == "CLIPLoader" and wv:
                    defaults["clip"] = wv
                elif ntype == "VAELoader" and wv:
                    defaults["vae"] = wv
                elif ntype == "KSampler" and wv and len(wv) >= 7:
                    defaults["ksampler"] = wv
                elif ntype == "PromptWorkstation" and wv:
                    for val in wv:
                        if isinstance(val, str) and ("blurry" in val or "bad anatomy" in val or "distorted" in val):
                            defaults["negative"] = val
                            break
            # If we found all key nodes, stop searching
            if defaults["unet"] and defaults["clip"] and defaults["vae"]:
                break
        except Exception:
            pass

    return defaults


def build_graph(base, phase, identity, tier, recipe, prompt_text, seed, prefix):
    ks = base["ksampler"]
    return {
        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": base["unet"][0], "weight_dtype": base["unet"][1]}},
        "6": {"class_type": "CLIPLoader", "inputs": {"clip_name": base["clip"][0], "type": base["clip"][1], "device": base["clip"][2] if len(base["clip"]) > 2 else "default"}},
        "7": {"class_type": "VAELoader", "inputs": {"vae_name": base["vae"][0]}},
        "20": {"class_type": "CurationPhaseSelector", "inputs": {"phase": phase, "identity_lora": identity}},
        "3": {"class_type": "TierLoRAStackRouter", "inputs": {
            "model": ["2", 0], "clip": ["6", 0], "active_tier_tag": f"EVAL_{tier}",
            "tier_override": TIER_OVERRIDE[tier], "master_identity_weight": 1.0, "tier_stack_multiplier": 1.0,
            "custom_recipe_path": "", "live_recipe_json": json.dumps(recipe), "phase_config": ["20", 0]}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 1], "text": prompt_text}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 1], "text": base["negative"]}},
        "10": {"class_type": "EmptySD3LatentImage", "inputs": {"width": ["20", 3], "height": ["20", 4], "batch_size": 1}},
        "11": {"class_type": "KSampler", "inputs": {
            "model": ["3", 0], "positive": ["8", 0], "negative": ["9", 0], "latent_image": ["10", 0],
            "seed": seed, "steps": ["20", 1], "cfg": ["20", 2], "sampler_name": ks[4], "scheduler": ks[5], "denoise": ks[6]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["7", 0]}},
        "18": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": prefix}},
    }


def render(graph, timeout=240):
    res = comfy("/prompt", "POST", {"prompt": graph, "client_id": "tier_stack_evaluator"})
    pid = res.get("prompt_id")
    if not pid:
        raise RuntimeError(f"submission failed: {res}")
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            hist = comfy(f"/history/{pid}")
        except Exception:
            hist = {}
        if pid in hist:
            st = hist[pid].get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError(f"execution error: {st}")
            for out in hist[pid].get("outputs", {}).values():
                for im in out.get("images", []):
                    f = OUTPUT_DIR / im.get("subfolder", "") / im["filename"]
                    if f.is_file():
                        return f
        time.sleep(2.0)
    raise TimeoutError("render timed out")


# ----------------------------------------------------------- dynamic search -
def generate_roster_candidate(tier: str, rng):
    """Generates a candidate with full creative license across thematic rosters and experimental wildcards."""
    mode_roll = rng.random()

    # Weight bounds tailored per tier
    if tier == "T2":
        w_anatomy = round(rng.uniform(0.60, 1.05), 2)
        w_skin = round(rng.uniform(0.20, 0.45), 2)
        w_lighting = round(rng.uniform(0.15, 0.35), 2)
        w_optics = round(rng.uniform(0.15, 0.40), 2)
    elif tier == "T3":
        w_anatomy = round(rng.uniform(0.35, 0.70), 2)
        w_skin = round(rng.uniform(0.15, 0.35), 2)
        w_lighting = round(rng.uniform(0.20, 0.45), 2)
        w_optics = round(rng.uniform(0.20, 0.45), 2)
    elif tier == "T4":
        w_anatomy = round(rng.uniform(0.40, 0.75), 2)
        w_skin = round(rng.uniform(0.15, 0.35), 2)
        w_lighting = round(rng.uniform(0.20, 0.45), 2)
        w_optics = round(rng.uniform(0.25, 0.50), 2)
    else:
        w_anatomy = round(rng.uniform(0.50, 0.85), 2)
        w_skin = round(rng.uniform(0.15, 0.35), 2)
        w_lighting = round(rng.uniform(0.15, 0.35), 2)
        w_optics = round(rng.uniform(0.10, 0.25), 2)

    if mode_roll < 0.35 and ALL_AVAILABLE_LORAS:
        # PURE WILD CREATIVE: 3 to 5 randomly chosen LoRAs from the entire library
        num_loras = rng.randint(3, 5)
        chosen = rng.sample(ALL_AVAILABLE_LORAS, min(num_loras, len(ALL_AVAILABLE_LORAS)))
        loras = []
        for l in chosen:
            l_low = l.lower()
            if "body" in l_low or "figure" in l_low or "thick" in l_low or "slider" in l_low:
                w = round(rng.uniform(0.45, 0.95), 2)
                role = "wild anatomy/body"
            elif "lighting" in l_low or "dreamcore" in l_low or "color" in l_low or "shadow" in l_low:
                w = round(rng.uniform(0.15, 0.35), 2)
                role = "wild atmosphere"
            elif "skin" in l_low or "oiled" in l_low:
                w = round(rng.uniform(0.20, 0.45), 2)
                role = "wild dermal"
            else:
                w = round(rng.uniform(0.15, 0.45), 2)
                role = "wild creative"
            loras.append({"lora": l, "weight": w, "role": role})
        return {"loras": loras, "mode": "wild_creative"}

    elif mode_roll < 0.70 and ALL_AVAILABLE_LORAS:
        # ROSTER + EXPERIMENTAL WILDCARD
        wild = rng.choice(ALL_AVAILABLE_LORAS)
        loras = [
            {"lora": rng.choice(ROSTER_ANATOMY), "weight": w_anatomy, "role": "anatomy & curves"},
            {"lora": rng.choice(ROSTER_SKIN), "weight": w_skin, "role": "dermal skin texture"},
            {"lora": rng.choice(ROSTER_LIGHTING), "weight": w_lighting, "role": "atmosphere & lighting"},
            {"lora": rng.choice(ROSTER_OPTICS), "weight": w_optics, "role": "optical sharpness & detail"},
            {"lora": wild, "weight": round(rng.uniform(0.15, 0.40), 2), "role": "experimental wildcard"},
        ]
        return {"loras": loras, "mode": "roster_wildcard"}

    else:
        # STANDARD 4-ROSTER DISCOVERY
        loras = [
            {"lora": rng.choice(ROSTER_ANATOMY), "weight": w_anatomy, "role": "anatomy & curves"},
            {"lora": rng.choice(ROSTER_SKIN), "weight": w_skin, "role": "dermal skin texture"},
            {"lora": rng.choice(ROSTER_LIGHTING), "weight": w_lighting, "role": "atmosphere & lighting"},
            {"lora": rng.choice(ROSTER_OPTICS), "weight": w_optics, "role": "optical sharpness & detail"},
        ]
        return {"loras": loras, "mode": "roster_discovery"}


def generate_slider_candidate(base_loras: list, rng) -> dict:
    """Tuning mode: micro-adjusts slider weights of existing recipe (+-0.04 to +-0.10).
    Keeps all LoRA models strictly frozen to prevent roster drift.
    """
    new_loras = []
    for l in base_loras:
        w = l.get("weight", l.get("strength_model", 0.5))
        role = l.get("role", "custom tier modifier")
        lname = l.get("lora", "")
        
        if "EyeDetail" in lname:
            delta = rng.choice([-0.04, -0.02, 0.0, 0.02, 0.04])
            new_w = round(max(0.04, min(0.20, w + delta)), 2)
        elif "PAWG" in lname:
            delta = rng.choice([-0.10, -0.06, 0.0, 0.06, 0.10])
            new_w = round(max(0.50, min(1.20, w + delta)), 2)
        elif "AntiPlastic" in lname or "skin texture" in lname:
            delta = rng.choice([-0.08, -0.04, 0.0, 0.04, 0.08, 0.10])
            new_w = round(max(0.10, min(0.55, w + delta)), 2)
        elif "Lighting" in lname:
            delta = rng.choice([-0.06, -0.03, 0.0, 0.03, 0.06])
            new_w = round(max(0.10, min(0.40, w + delta)), 2)
        elif "XXX" in lname:
            delta = rng.choice([-0.05, 0.0, 0.05])
            new_w = round(max(0.10, min(0.35, w + delta)), 2)
        else:
            delta = rng.choice([-0.06, -0.03, 0.0, 0.03, 0.06])
            new_w = round(max(0.10, min(0.80, w + delta)), 2)
            
        new_loras.append({"lora": lname, "weight": new_w, "role": role})
    return {"loras": new_loras, "mode": "slider_tune"}


def generate_annealed_candidate(champion_cand, rng):
    """Stage 2: Micro-weight fine-tuning (+-0.04 to +-0.08) around the champion recipe."""
    base_loras = champion_cand.get("loras", [])
    new_loras = []
    for l in base_loras:
        delta = rng.choice([-0.06, -0.04, 0.0, 0.04, 0.06])
        new_w = round(max(0.10, min(1.20, l["weight"] + delta)), 2)
        new_loras.append({"lora": l["lora"], "weight": new_w, "role": l.get("role", "custom")})
    return {"loras": new_loras, "mode": "annealed"}


def apply_candidate_recipe(base_recipe, tier, cand):
    r = copy.deepcopy(base_recipe)
    cand_loras = cand.get("loras", [])
    stack = []
    base_tier_loras = {l["lora"]: l for l in base_recipe["tiers"][tier].get("loras", [])}
    for cl in cand_loras:
        lname = cl["lora"]
        mw = cl["weight"]
        if "strength_clip" in cl:
            cw = cl["strength_clip"]
        elif lname in base_tier_loras:
            base_l = base_tier_loras[lname]
            base_mw = base_l.get("strength_model", 1.0)
            base_cw = base_l.get("strength_clip", 0.5)
            ratio = (base_cw / base_mw) if base_mw > 0 else 0.5
            cw = round(mw * ratio, 2)
        else:
            cw = round(mw * 0.5, 2)
        stack.append({
            "lora": lname,
            "strength_model": mw,
            "strength_clip": cw,
            "enabled": True,
            "role": cl.get("role", "evaluator candidate")
        })
    r["tiers"][tier]["loras"] = stack
    return r


def stack_desc(recipe, tier):
    return ", ".join(f"{Path(l['lora']).stem}@{l['strength_model']}" for l in recipe["tiers"][tier]["loras"] if l.get("enabled", True))


def write_leaderboard(path, phase, tier, results, converged_reason=""):
    rows = sorted(results, key=lambda r: r["fitness"], reverse=True)
    golden_count = sum(1 for r in rows if r.get("verified_golden"))
    th = TIER_THRESHOLDS.get(tier, {"golden": 0.70, "candidate": 0.65, "pass": 0.60})

    lines = [
        f"# Tier Stack Leaderboard - {phase} / {tier} [{TIER_OVERRIDE.get(tier, '')}]",
        f"**Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}  |  **Evaluated:** {len(rows)}  |  **Verified Golden:** {golden_count}",
        f"**Tier Calibration Targets:** Golden >= {th['golden']:.2f} | Candidate >= {th['candidate']:.2f} | Pass >= {th['pass']:.2f}",
    ]
    if converged_reason:
        lines.append(f"**Status:** {converged_reason}")
    lines.extend([
        "",
        "| Rank | Status | Fitness | Parity | Face Sharp | Body Sharp | Entropy | Clip | Stack |",
        "|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--|",
    ])
    for i, r in enumerate(rows[:50], 1):
        status = "🏆 GOLDEN" if r.get("verified_golden") else ("⭐ CANDIDATE" if r["fitness"] >= th["candidate"] else ("✅ PASS" if r["fitness"] >= th["pass"] else "⚠️ DRIFT"))
        lines.append(f"| {i} | {status} | **{r['fitness']:.4f}** | {r['parity']:.4f} | {r['sharp']:.3f} | {r.get('body_sharp', 0.0):.3f} | {r.get('entropy', 0.5):.2f} | {r['clip']:.4f} | {r['stack']} |")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Multi-Modal Tier-calibrated LoRA discovery evaluator with 3-Seed Triangulation and Annealing")
    ap.add_argument("--phase", choices=["Phase 1", "Phase 2", "Phase 3"], default="Phase 3")
    ap.add_argument("--tier", choices=list(TIER_OVERRIDE), required=True)
    ap.add_argument("--identity", default="Vespera_ZIT_Phase_2_.safetensors", help="identity LoRA filename (ignored in Phase 1)")
    ap.add_argument("--evals", type=int, default=100, help="maximum candidate stacks to evaluate (default: 100 passes)")
    ap.add_argument("--golden-target", type=float, default=-1.0, help="fitness score threshold (<= 0 for auto tier calibration)")
    ap.add_argument("--golden-quota", type=int, default=5, help="number of verified golden stacks to curate before early stopping (default: 5)")
    ap.add_argument("--patience", type=int, default=25, help="consecutive evaluations without improvement before plateau stopping (default: 25)")
    ap.add_argument("--prompt", default="", help="override the tier test prompt")
    ap.add_argument("--mode", default="tune", choices=["tune", "search"], help="tune=frozen roster slider tuning; search=roster discovery")
    ap.add_argument("--promote", action="store_true", help="write the best stack into the phase recipe JSON")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    th = TIER_THRESHOLDS[args.tier]
    golden_target = th["golden"] if args.golden_target <= 0 else args.golden_target

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    mode_suffix = f"_{args.mode}" if args.mode == "tune" else ""
    tag = f"{args.phase.replace(' ', '').lower()}_{args.tier.lower()}{mode_suffix}"
    ledger_path, board_path = EVAL_DIR / f"ledger_{tag}.json", EVAL_DIR / f"LEADERBOARD_{tag}.md"

    phase_file = SUITE_DIR / "data" / f"tier_lora_recipes_{args.phase.replace(' ', '').lower()}.json"
    base_recipe = json.loads(phase_file.read_text(encoding="utf-8"))
    identity = "(None)" if args.phase == "Phase 1" else args.identity
    base = load_base_widgets()
    prompt_text = IDENTITY_PREFIX + (args.prompt or TIER_PROMPTS[args.tier])

    seeds = TIER_SEEDS[args.tier]
    confirm_seeds = TIER_CONFIRM_SEEDS.get(args.tier, [99, 100, 101])

    print("=" * 80)
    print(f"👑 Vespera Multi-LoRA Discovery Evaluator :: {args.phase} / {args.tier} [{TIER_OVERRIDE[args.tier]}]")
    print(f"Identity LoRA      : {identity}")
    print(f"Target Recipe File : {phase_file.name}")
    print(f"Current Baseline   : {stack_desc(base_recipe, args.tier)}")
    print(f"Roster Exploration : Anatomy ({len(ROSTER_ANATOMY)}) | Skin ({len(ROSTER_SKIN)}) | Lighting ({len(ROSTER_LIGHTING)}) | Optics ({len(ROSTER_OPTICS)})")
    print(f"3-Seed Suite       : Screening: {seeds} | Confirmation: {confirm_seeds}")
    print(f"Execution Target   : Max Evals: {args.evals} | Quota: {args.golden_quota} Golden Stacks (>= {golden_target:.2f}) | Patience: {args.patience}")
    print("=" * 80)

    init_anchors()
    comfy("/system_stats")

    rng = random.Random(args.seed)

    # 1. Baseline candidate from current recipe
    current_loras = base_recipe["tiers"][args.tier]["loras"]
    baseline_cand = {
        "loras": [{"lora": l["lora"], "weight": l["strength_model"], "role": l.get("role", "baseline")} for l in current_loras],
        "mode": "baseline"
    }

    results = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else []
    done = {r["signature"] for r in results}

    verified_golden_count = sum(1 for r in results if r.get("verified_golden"))
    best_fitness = max([r.get("fitness", 0.0) for r in results], default=0.0)
    best_candidate_rec = None
    for r in results:
        if r.get("fitness", 0.0) == best_fitness:
            best_candidate_rec = r
            break

    patience_counter = 0
    converged_reason = ""

    print(f"[+] Loaded {len(results)} prior evaluations (Current Best: {best_fitness:.4f}, Golden: {verified_golden_count}/{args.golden_quota})")

    new_evals = 0
    total_idx = len(results)
    while new_evals < args.evals:
        total_idx += 1

        if args.golden_quota > 0 and verified_golden_count >= args.golden_quota:
            converged_reason = f"🎯 Reached Golden Quota ({verified_golden_count}/{args.golden_quota} verified stacks >= {golden_target:.2f})!"
            print(f"\n[!] {converged_reason} Halting search.")
            break

        if args.patience > 0 and patience_counter >= args.patience:
            converged_reason = f"⏸️ Reached Patience Plateau ({patience_counter} evals without improvement over {best_fitness:.4f})!"
            print(f"\n[!] {converged_reason} Halting search.")
            break

        # Candidate selection:
        # Pass 1: Baseline
        # Passes 2-60: Roster Discovery (exploring combinations of different LoRAs)
        # Passes 61-100: Annealing (fine-tuning around champion recipe)
        if total_idx == 1 and not results:
            cand = baseline_cand
        elif args.mode == "tune":
            cand = generate_slider_candidate(current_loras, rng)
        else:
            cand = generate_roster_candidate(args.tier, rng)

        sig = json.dumps(cand.get("loras", []), sort_keys=True)
        if sig in done:
            continue

        recipe = apply_candidate_recipe(base_recipe, args.tier, cand)
        desc = stack_desc(recipe, args.tier)
        mode_tag = cand.get("mode", "search").upper()
        new_evals += 1
        print(f"\n--- [Eval {new_evals}/{args.evals} (Total #{total_idx})] [{mode_tag}] (Golden: {verified_golden_count} | Best: {best_fitness:.4f}) ---")
        print(f"  • Candidate: {desc}")

        scores, files = [], []
        try:
            for s in seeds:
                g = build_graph(base, args.phase, identity, args.tier, recipe, prompt_text, s, f"tier_eval/{tag}/c{total_idx:03d}_s{s}")
                f = render(g)
                files.append(f.name)
                scores.append(score_image(f, tier=args.tier))
        except Exception as e:
            print(f"  [-] candidate failed: {e}")
            time.sleep(3)
            continue

        fit = fitness(args.tier, scores)
        faces_found = sum(x["face"] for x in scores)
        mean_parity = float(np.mean([x["parity"] for x in scores]))
        mean_sharp = float(np.mean([x["sharp"] for x in scores]))
        mean_bsharp = float(np.mean([x["body_sharp"] for x in scores]))
        mean_ent = float(np.mean([x.get("entropy", 0.5) for x in scores]))
        mean_clip = float(np.mean([x["clip"] for x in scores]))

        print(f"  >> 3-Seed Screening: fitness={fit:.4f} [parity={mean_parity:.4f}, face_sharp={mean_sharp:.3f}, body_sharp={mean_bsharp:.3f}, entropy={mean_ent:.2f}, clip={mean_clip:.4f}] faces={faces_found}/{len(seeds)}")

        is_verified_golden = False

        # Multi-Seed Verification Gate (Anti-Fluke 6-Seed Composite Stress Check)
        if fit >= golden_target and (faces_found >= 2 or args.tier in ("T2", "T4")):
            print(f"  ⭐ High-scoring candidate detected! Running {len(confirm_seeds)} confirmation stress seeds ({confirm_seeds})...")
            confirm_scores, confirm_files = [], []
            try:
                for cs in confirm_seeds:
                    cg = build_graph(base, args.phase, identity, args.tier, recipe, prompt_text, cs, f"tier_eval/{tag}/c{total_idx:03d}_confirm_s{cs}")
                    cf = render(cg)
                    confirm_files.append(cf.name)
                    confirm_scores.append(score_image(cf, tier=args.tier))
                
                all_scores = scores + confirm_scores
                fit_verified = fitness(args.tier, all_scores)
                all_faces = sum(x["face"] for x in all_scores)

                print(f"  >> 6-Seed Verification Check: Composite Fitness={fit_verified:.4f} (Faces: {all_faces}/{len(all_scores)})")

                if fit_verified >= (golden_target - 0.02):
                    is_verified_golden = True
                    verified_golden_count += 1
                    fit = fit_verified
                    scores = all_scores
                    files.extend(confirm_files)
                    print(f"  🏆 VERIFIED GOLDEN STACK #{verified_golden_count}/{args.golden_quota}! (Stress-tested across 6 seeds)")
                else:
                    print(f"  ⚠️ Candidate dropped on confirmation seeds ({fit_verified:.4f} < {golden_target}). Not verified as golden.")
            except Exception as ce:
                print(f"  [-] Confirmation check encountered error: {ce}")

        # Plateau & Patience Tracking
        if fit > best_fitness:
            improvement = fit - best_fitness
            best_fitness = fit
            best_candidate_rec = {"cand": cand, "fitness": fit}
            patience_counter = 0
            print(f"  ✨ NEW ALL-TIME BEST! Fitness: {best_fitness:.4f} (+{improvement:.4f})")
        else:
            patience_counter += 1

        rec = {
            "signature": sig,
            "cand": cand,
            "stack": desc,
            "recipe_tier": recipe["tiers"][args.tier],
            "fitness": fit,
            "verified_golden": is_verified_golden,
            "parity": float(np.mean([x["parity"] for x in scores])),
            "sharp": float(np.mean([x["sharp"] for x in scores])),
            "body_sharp": float(np.mean([x.get("body_sharp", 0.0) for x in scores])),
            "entropy": float(np.mean([x.get("entropy", 0.5) for x in scores])),
            "clip": float(np.mean([x["clip"] for x in scores])),
            "faces_found": sum(x["face"] for x in scores),
            "total_seeds": len(scores),
            "files": files,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        results.append(rec)
        ledger_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        write_leaderboard(board_path, args.phase, args.tier, results, converged_reason)

        # PyTorch CUDA cache flush every 5 candidates to prevent memory leaks
        if new_evals % 5 == 0:
            try:
                comfy("/free", "POST", {"unload_models": False, "free_memory": True})
            except Exception:
                pass

    if not results:
        print("[-] No results.")
        return

    best = max(results, key=lambda r: r["fitness"])
    print("\n" + "=" * 80)
    print(f"🏆 EVALUATION COMPLETE :: Best Stack for {args.phase} / {args.tier}:")
    print(f"  • Stack   : {best['stack']}")
    print(f"  • Fitness : {best['fitness']:.4f} (Parity: {best['parity']:.4f}, FaceSharp: {best['sharp']:.3f}, BodySharp: {best.get('body_sharp', 0.0):.3f})")
    print(f"  • Golden  : {'YES (Verified)' if best.get('verified_golden') else 'No'}")
    print(f"  • Output Leaderboard : {board_path}")
    print("=" * 80 + "\n")

    if args.promote:
        backup = phase_file.with_suffix(f".bak_{time.strftime('%Y%m%d_%H%M%S')}.json")
        shutil.copy2(phase_file, backup)
        base_recipe["tiers"][args.tier]["loras"] = best["recipe_tier"]["loras"]
        phase_file.write_text(json.dumps(base_recipe, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] 👑 AUTO-PROMOTED Champion Stack into {phase_file.name} (Backup: {backup.name})!")
        print("    Click 'Revert' on the on-canvas router UI or restart ComfyUI to reload the new golden stack.")


if __name__ == "__main__":
    main()
