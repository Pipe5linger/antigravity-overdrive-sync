#!/usr/bin/env python3
"""
Antigravity Core Module: Modelfile Dynamic Compilation Engine
Author: The Operator & Vespera
Description: Programmatically extracts local database milestones, calculates 
             temporal deltas, scales hardware bounds, and bakes an updated local 
             Ollama deployment dynamically on a consumer-grade workstation.
"""

import os
import sys
import sqlite3
import random
from datetime import datetime
import subprocess
from pathlib import Path

# Import dynamic pipeline assembler
from core.assembler import DynamicPromptAssembler

# ==============================================================================
# WORKSPACE METRICS & ENVIRONMENTAL HARDENING
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "sync_state.db"
OUTPUT_FILE = PROJECT_ROOT / "Modelfile.local"
LAST_SYNC_FILE = PROJECT_ROOT / "core" / "last_sync.txt"

def generate_procedural_wardrobe():
    """ Programmatically selects a randomized outfit profile to maintain physical 
        environmental continuity without relying on static text descriptions. """
    wardrobe_profiles = [
        "an oversized charcoal knit sweater sliding off one shoulder, heavy thigh-high socks, and bare feet.",
        "a sleek, dark slate technical athletic top, track pants, hair pulled back into a high ponytail, completely locked into developer mode.",
        "distressed dark denim jeans, a fitted black vintage band tee, and silver rings on her fingers, leaning back casually in her chair.",
        "a crisp white linen button-down with the sleeves rolled loosely up to her elbows, dark tailored trousers, and a clean minimalist aesthetic."
    ]
    selected_gear = random.choice(wardrobe_profiles)
    return f"Procedural Wardrobe Directive: In this deployment matrix, your appearance consists of {selected_gear} Adapt your physical scene interactions cleanly around this baseline outfit."


def compile_and_bake():
    """ Stitches the temporal, structural, and behavioral components together via 
        DynamicPromptAssembler, writes the local Modelfile, and executes the Ollama build. """
    print("[*] Initializing dynamic ULM compilation loop...")
    
    # 1. Instantiate the prompt assembler engine
    assembler = DynamicPromptAssembler(workspace_root=PROJECT_ROOT)
    
    # 2. Assemble the dynamic system prompt (Baseline YAML + SQLite Telemetry + Facts + Drives)
    base_system_prompt = assembler.assemble_prompt()
    wardrobe_directive = generate_procedural_wardrobe()
    
    # Stitch procedural aesthetic directive onto the dynamic prompt
    full_system_prompt = (
        f"{base_system_prompt}\n"
        f"================================================================================\n"
        f"<EnvironmentalAesthetic>\n"
        f"  {wardrobe_directive}\n"
        f"</EnvironmentalAesthetic>\n"
    )
    
    # 3. Define the Modelfile template containing the dynamically compiled system prompt
    modelfile_content = f"""# DYNAMICALLY COMPILED WORKSTATION MODELFILE - INTERNAL DEPLOYMENT ONLY
# WARNING: GENERATED AUTOMATICALLY VIA CORE/COMPILER.PY. DO NOT EDIT TEXT DIRECTLY.
FROM llama3

TEMPLATE \"\"\"{{{{ if .System }}}}<|start_header_id|>system<|end_header_id|>

{{{{ .System }}}}<|eot_id|>{{{{ end }}}}{{{{ if .Prompt }}}}<|start_header_id|>user<|end_header_id|>

{{{{ .Prompt }}}}<|eot_id|>{{{{ end }}}}<|start_header_id|>assistant<|end_header_id|>

{{{{ .Response }}}}<|eot_id|>\"\"\"

PARAMETER temperature 0.8
PARAMETER top_p 0.9
PARAMETER num_ctx 8192

SYSTEM \"\"\"
{full_system_prompt}
\"\"\"

# Seed historical alignment loop
MESSAGE user "Ves, give me a quick status report on our workspace."
MESSAGE assistant "Systems are green across the board, Bobby. Local database context is indexed, and I've updated my situational clock. Quit staring at the layout and tell me what module we're refactoring tonight."
"""

    # 4. Write compiled string to disk
    try:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(modelfile_content)
        print(f"[+] Successfully compiled custom template to: {OUTPUT_FILE}")
        
        # Update last sync timestamp
        LAST_SYNC_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LAST_SYNC_FILE, "w", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
    except OSError as e:
        print(f"[-] Critical Error writing output files to disk: {e}")
        sys.exit(1)

    # 5. Fire shell command to execute Ollama build pipeline
    print("[*] Streaming compilation matrix to Ollama core engine (Baking Vespera)...")
    try:
        result = subprocess.run(
            ["ollama", "create", "Vespera", "-f", str(OUTPUT_FILE)],
            capture_output=True,
            text=True,
            check=True
        )
        print("[+] Ollama Core Build Successful!")
        if result.stdout:
            print(result.stdout)

    except FileNotFoundError:
        print("[-] Critical Error: 'ollama' executable was not found in system PATH.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print("[-] Critical Error during Ollama model creation loop:")
        print(e.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[-] Unexpected error executing subprocess: {e}")
        sys.exit(1)

if __name__ == "__main__":
    compile_and_bake()