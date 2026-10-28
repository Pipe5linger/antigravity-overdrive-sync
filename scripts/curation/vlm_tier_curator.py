"""
vlm_tier_curator.py
===================
Semantic VLM Dataset Curator using Vision-Language Models (Ollama Qwen2.5-VL / LLaVA).

Why this replaces classical OpenCV:
-----------------------------------
Traditional CV (Haar cascades, Laplacian blur, HSV thresholds) has zero semantic understanding:
it mistakes textured wallpaper for skin, can't tell an awkward blink from a genuine smile, and 
fails on complex lighting.

A Vision-Language Model (VLM) evaluates images with human-level aesthetic and anatomical intelligence:
  - Validates genuine subject visibility & likeness
  - Recognizes true photographic framing (Close-up Macro vs Cowboy/Torso vs Full-Length)
  - Scores flattery, lighting quality, and facial expression naturally
  - Understands wardrobe styling and posture dynamics
  - Sorts cleanly into the 4 ZIT Pose & Action Engine Tiers:
      * Tier 1: Identity Anchors (Macro & Close-Up Face Portraits)
      * Tier 2: Raw Anatomy (Torso, Mid-shots, Curves, Natural Proportions)
      * Tier 3: Wardrobe Agnosticism (Diverse Outfits, Fabrics, Styling)
      * Tier 4: 3D Spatial Awareness (Full-Length Head-to-Toe, Motion, Perspective)

Usage:
------
python vlm_tier_curator.py --input_dir <path> --output_dir <path> --model qwen2.5vl:3b
"""

import os
import sys
import json
import time
import base64
import shutil
import argparse
import urllib.request
from io import BytesIO
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


VLM_PROMPT = """Analyze this photograph for a character reference dataset.
Evaluate the subject and return ONLY a valid JSON object matching this schema:
{
  "subject_visible": true,
  "framing": "close_up" | "bust" | "half_body" | "full_body",
  "tier": "Tier 1: Identity Anchor" | "Tier 2: Raw Anatomy" | "Tier 3: Wardrobe" | "Tier 4: 3D Spatial",
  "flattery_score": <float 1.0 to 10.0, evaluating beauty, focus, and lighting>,
  "sharpness": "high" | "medium" | "low",
  "angle": "frontal" | "3/4 left" | "3/4 right" | "profile" | "back",
  "expression": "neutral" | "smile" | "playful" | "candid" | "unflattering",
  "wardrobe_description": "<brief description of clothing>",
  "suitable_as_anchor": true | false,
  "reason": "<short explanation>"
}

Tier Guidance:
- Tier 1: Close-up macro face portraits, tight headshots, clear eyes/lips/micro-texture.
- Tier 2: Mid-range cowboy/torso shots highlighting natural body proportions, waist-to-hip ratio, bust, or posture.
- Tier 3: Outfits, jackets, dresses, distinct clothing styles and textures.
- Tier 4: Full-length head-to-toe shots, dynamic movement, environmental depth, or full silhouette.

Output strictly raw JSON without markdown code fences or conversational text."""


class VLMTierCurator:
    def __init__(self, input_dir, output_dir, model="qwen2.5vl:3b", ollama_url="http://localhost:11434", quotas=None):
        self.input_dir = os.path.abspath(input_dir)
        self.output_dir = os.path.abspath(output_dir)
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.quotas = quotas or {"tier1": 15, "tier2": 10, "tier3": 15, "tier4": 10}

    def encode_image(self, fpath, max_dim=768):
        """Downscales image to max_dim for rapid VLM inference and returns base64 string."""
        with Image.open(fpath) as im:
            # Convert RGBA/P to RGB
            if im.mode != "RGB":
                im = im.convert("RGB")
            w, h = im.size
            scale = float(max_dim) / max(w, h)
            if scale < 1.0:
                im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("utf-8")

    def query_vlm(self, base64_image):
        """Queries local Ollama VLM with image payload."""
        payload = {
            "model": self.model,
            "prompt": VLM_PROMPT,
            "images": [base64_image],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 300
            }
        }
        
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                raw_txt = res_data.get("response", "").strip()
                
                # Strip markdown code blocks if VLM outputs them
                if raw_txt.startswith("```"):
                    raw_txt = raw_txt.strip("`")
                    if raw_txt.startswith("json"):
                        raw_txt = raw_txt[4:].strip()
                
                # Parse JSON
                return json.loads(raw_txt)
        except Exception as e:
            return {"error": str(e), "raw": raw_txt if 'raw_txt' in locals() else None}

    def run(self):
        print("==================================================")
        print("VLM Semantic Tier-Matrix Curator")
        print(f"Model       : {self.model}")
        print(f"Input Pool  : {self.input_dir}")
        print(f"Output Base : {self.output_dir}")
        print("==================================================")

        files = sorted([f for f in os.listdir(self.input_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])
        print(f"Discovered {len(files)} files to evaluate with {self.model}...")

        results = []
        t0 = time.time()

        for idx, fname in enumerate(files, 1):
            fp = os.path.join(self.input_dir, fname)
            try:
                b64_img = self.encode_image(fp)
                analysis = self.query_vlm(b64_img)
                analysis["filename"] = fname
                analysis["filepath"] = fp
                results.append(analysis)
                
                tier = analysis.get("tier", "Unknown")
                score = analysis.get("flattery_score", 0)
                expr = analysis.get("expression", "")
                print(f"[{idx:4d}/{len(files)}] {fname:<24} | {tier:<20} | Score: {score} | Expr: {expr}")
            except Exception as e:
                print(f"[{idx:4d}/{len(files)}] Error on {fname}: {e}")

        # Save complete raw VLM analysis
        os.makedirs(self.output_dir, exist_ok=True)
        report_path = os.path.join(self.output_dir, "vlm_analysis_master.json")
        with open(report_path, "w", encoding="utf-8") as jf:
            json.dump(results, jf, indent=2)

        # Harvest into Tiers based on VLM semantic judgement
        tier_map = {
            "Tier 1: Identity Anchor": ("Tier1_Identity_Anchors", self.quotas["tier1"]),
            "Tier 2: Raw Anatomy": ("Tier2_Raw_Anatomy", self.quotas["tier2"]),
            "Tier 3: Wardrobe": ("Tier3_Wardrobe_Agnosticism", self.quotas["tier3"]),
            "Tier 4: 3D Spatial": ("Tier4_3D_Spatial", self.quotas["tier4"])
        }

        print("\nHarvesting Golden Selections into Tier Vaults:")
        for tier_key, (folder_name, quota) in tier_map.items():
            tier_pool = [r for r in results if r.get("tier") == tier_key and r.get("suitable_as_anchor", True)]
            tier_pool.sort(key=lambda x: float(x.get("flattery_score", 0)), reverse=True)
            
            chosen = tier_pool[:quota]
            dst_dir = os.path.join(self.output_dir, folder_name)
            os.makedirs(dst_dir, exist_ok=True)
            
            for item in chosen:
                shutil.copy2(item["filepath"], os.path.join(dst_dir, item["filename"]))
                
            print(f"  {folder_name:<28}: Harvested {len(chosen)}/{quota} top-rated candidates")

        print(f"\nVLM Evaluation Complete in {time.time() - t0:.1f}s!")


def main():
    parser = argparse.ArgumentParser(description="VLM Semantic Tier-Matrix Curator")
    parser.add_argument("--input_dir", default=r"D:\AI\Projects\ComfyUI\input\Amy_Raw_Staging\all")
    parser.add_argument("--output_dir", default=r"D:\AI\Projects\ComfyUI\input\Amy_Raw_Staging\Tier_Anchors_VLM")
    parser.add_argument("--model", default="qwen2.5vl:3b")
    parser.add_argument("--ollama_url", default="http://localhost:11434")

    args = parser.parse_args()
    curator = VLMTierCurator(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        model=args.model,
        ollama_url=args.ollama_url
    )
    curator.run()


if __name__ == "__main__":
    main()

