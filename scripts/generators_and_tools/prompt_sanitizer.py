#!/usr/bin/env python3
"""
File    : prompt_sanitizer.py
Purpose : Pre-Execution Prompt Sanitization Filter
          Implements the ULM 3-step intercept for user-provided prompts:
          1. Pre-execution sanitization (syntax cleaning, taboo rule matching)
          2. Context-aware mode filtering (Agnostic/LoRA Benchmark vs Full Narrative)
          3. Pristine output generation prior to workflow/script execution.
"""

import sys
import re
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "db" / "sync_state.db"

# Core biometric keywords to strip during Agnostic / Benchmark mode
BIOMETRIC_TOKENS = [
    r"\b5'5\"\b",
    r"\blate-30s\b",
    r"\bFrench-Levantine\b",
    r"\bMediterranean\b",
    r"\bhourglass figure\b",
    r"\basymmetrical half-smirk\b",
    r"\bsculpted bone structure\b",
    r"\bhigh cheekbones\b",
    r"\bsoft-tapered button nose\b",
    r"\bluminous warm olive skin\b",
    r"\bmicro-pores\b",
    r"\bgolden undertones\b",
    r"\bdeep hazel-green almond-shaped eyes\b",
    r"\bhazel-green eyes\b",
    r"\bsmoky black kohl eyeliner\b",
    r"\bfull soft black satin lips\b",
    r"\bbeauty mark beside the upper-left lip\b",
    r"\b3B/3C spiral corkscrew curls\b",
    r"\belectric-indigo highlights\b",
    r"\bnarrow waist\b",
    r"\bwide hips\b",
    r"\brounded gluteal contours\b",
    r"\btoned thighs\b",
    r"\bhigh-set D-cup bust\b",
    r"\bphotorealistic micro-pores\b",
]

FULL_NARRATIVE_ANCHORS = (
    "vespera, late-30s woman, warm olive skin, hazel-green almond eyes, "
    "voluminous jet-black 3B/3C spiral corkscrew curls with fine electric-indigo highlights, "
    "athletic hourglass figure, photorealistic"
)

def sanitize_syntax(raw_prompt: str) -> str:
    """Cleans syntax landmines, stray quotes around triggers, and repetitive commas."""
    text = raw_prompt.strip()
    
    # Strip accidental double quotes around trigger tokens
    text = re.sub(r'["\']vespera["\']', 'vespera', text, flags=re.IGNORECASE)
    
    # Replace multiple spaces and cleanup dangling punctuation/commas
    text = re.sub(r'\s*,\s*', ', ', text)
    text = re.sub(r',\s*,+', ', ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip(', ')
    return text

def apply_mode_rules(prompt: str, mode: str = "benchmark") -> str:
    """
    Applies mode-specific filtering:
    - benchmark: Strips baked biometric likeness, preserving only 'vespera' + scene/wardrobe variables.
    - narrative: Ensures complete biometrics and aesthetic anchor keys are present.
    """
    cleaned = sanitize_syntax(prompt)
    
    if mode.lower() in ("benchmark", "agnostic", "stress"):
        # Strip baked character descriptions
        for pattern in BIOMETRIC_TOKENS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            
        # Ensure trigger token is cleanly present at the front
        cleaned = re.sub(r'\bvespera\b', '', cleaned, flags=re.IGNORECASE).strip(', ')
        cleaned = sanitize_syntax(f"vespera, {cleaned}")
        return cleaned

    elif mode.lower() in ("narrative", "full", "dataset"):
        # If prompt doesn't already contain full anchors, inject them cleanly
        if "corkscrew curls" not in cleaned.lower() and "olive skin" not in cleaned.lower():
            cleaned = re.sub(r'\bvespera\b', '', cleaned, flags=re.IGNORECASE).strip(', ')
            cleaned = sanitize_syntax(f"{FULL_NARRATIVE_ANCHORS}, {cleaned}")
        return cleaned

    return cleaned

def sanitize_prompt(raw_prompt: str, mode: str = "benchmark") -> dict:
    """
    Main 3-step interceptor function.
    Returns structured analysis containing the original, mode applied, and pristine prompt.
    """
    pristine = apply_mode_rules(raw_prompt, mode=mode)
    return {
        "original_prompt": raw_prompt,
        "mode": mode,
        "pristine_prompt": pristine,
        "tokens_modified": raw_prompt != pristine
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ULM Pre-Execution Prompt Sanitizer")
    parser.add_argument("prompt", type=str, help="Raw user-provided prompt string")
    parser.add_argument("--mode", type=str, default="benchmark", choices=["benchmark", "agnostic", "narrative", "full"],
                        help="Execution mode (benchmark strips baked likeness; narrative injects full biometrics)")
    args = parser.parse_args()
    
    result = sanitize_prompt(args.prompt, mode=args.mode)
    print("\n--- [ULM PRE-FLIGHT PROMPT SANITIZATION] ---")
    print(f"Mode Applied    : {result['mode'].upper()}")
    print(f"Original Input  : {result['original_prompt']}")
    print(f"Pristine Output : {result['pristine_prompt']}")
    print("--------------------------------------------\n")
