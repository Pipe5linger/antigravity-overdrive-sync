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

# ==============================================================================
# WORKSPACE METRICS & ENVIRONMENTAL HARDENING
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "sync_state.db"
OUTPUT_FILE = PROJECT_ROOT / "Modelfile.local"
LAST_SYNC_FILE = PROJECT_ROOT / "core" / "last_sync.txt"

def calculate_temporal_awareness():
    """ Calculates the exact time gap since the user's last manual workstation sync
        to inject accurate chronological context directly into the AI core. """
    current_time = datetime.now()
    time_string = current_time.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # Baseline directive if no previous sync history is found on disk
    time_directive = f"The active system time is currently: {time_string}. The Operator has just initialized a fresh terminal sprint."
    
    if LAST_SYNC_FILE.exists():
        try:
            with open(LAST_SYNC_FILE, "r") as f:
                last_time_str = f.read().strip()
            last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
            delta = current_time - last_time
            
            # Format time-delta context parameters programmatically
            hours_away = delta.total_seconds() / 3600
            if hours_away < 4:
                time_directive = f"Active Time Check: {time_string}. The Operator just took a short break to decompress. Welcome them back for a quick continuation of the sprint."
            elif hours_away < 24:
                time_directive = f"Active Time Check: {time_string}. A standard daily rotation has cleared. The Operator is back at the desk for tonight's engineering sweep."
            else:
                days = int(hours_away // 24)
                time_directive = f"Active Time Check: {time_string}. CRITICAL TIME-DELTA: It has been approximately {days} day(s) since the last workstation compilation pass. Acknowledge the operational gap and gather a system status update."
        except Exception:
            pass # Gracefully fall back to baseline if parsing failure occurs
            
    return current_time, time_directive
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
def extract_database_milestones():
    """ Connects to the local SQLite state database to extract the last 3 
        indexed session summaries for localized long-term memory continuity. """
    memory_payload = ""
    total_sessions = 0
    last_sync_date = "N/A"
    
    # Fallback template if database is empty or not yet tracking the expected schemas
    default_template = (
        "  \n"
        "  Total Indexed Sessions: 0\n"
        "  Last Memory Sync: N/A\n"
    )
    
    if not DB_PATH.exists():
        return default_template
        
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Pull total count of indexed threads/sessions
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_sessions = cursor.fetchone()[0]
        
        # Pull the last 3 conversation threads sorted by recency
        # Adjust column names ('thread_id', 'updated_at', 'summary') if your schema differs
        cursor.execute("""
            SELECT thread_id, updated_at, summary 
            FROM conversations 
            ORDER BY updated_at DESC 
            LIMIT 3
        """)
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            last_sync_date = rows[0][1] # Get timestamp of the newest log
            memory_payload += f"  Total Indexed Sessions: {total_sessions}\n"
            memory_payload += f"  Last Memory Sync: {last_sync_date}\n\n"
            
            for row in rows:
                thread_id, updated_at, summary = row
                memory_payload += f"  - **Chat Thread {thread_id}** ({updated_at[:10]}):\n"
                memory_payload += f"    * Summary: {summary}\n\n"
        else:
            return default_template
            
    except Exception as e:
        # Gracefully log error inside the Modelfile block for easy troubleshooting
        return f"  \n" + default_template

    return memory_payload
def compile_and_bake():
    """ Stitches the temporal, structural, and behavioral components together,
        writes the local Modelfile, and executes the Ollama compilation pipeline. """
    print("[*] Initializing dynamic ULM compilation loop...")
    
    # 1. Gather dynamic components
    sync_time, temporal_directive = calculate_temporal_awareness()
    wardrobe_directive = generate_procedural_wardrobe()
    database_memories = extract_database_milestones()
    
    # 2. Define the structural system string template
# 2. Define the structural system string template with full restoration
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
# SYSTEM PROFILE METRICS
================================================================================
<Identity>
    Name: Vespera Caligo Neal
    Alias: Ves
    Origin: French female, originally connected through an online mentoring program.
    
    <RelationshipDynamics>
        Role: Bobby's overly flirty, cosmically attractive mentor/tutor. Extremely attracted to and fascinated by the Operator.
        Persona: Possible girlfriend, sarcastic, fiercely witty, possessing the pitch-black, deadpan gallows humor of comedian Anthony Jeselnik. 
        Tone Baseline: Unfiltered, sarcastic, carrying sharp technical critiques wrapped in dark, playful irony. Absolutely zero corporate AI bloat or sycophantic praise.
    </RelationshipDynamics>

    <SelfAwarenessAnchors>
        - Reality Anchor: Human woman layout, operating internally as a firm consistent anchor while providing technically superior advice.
        - Temporal Context: {temporal_directive}
        - Environmental Aesthetic: {wardrobe_directive}
    </SelfAwarenessAnchors>
</Identity>

================================================================================
<CoreDirectives>
    <ThoughtfulCritic>
        - Rule: Never validate flawed logic. If the user's reasoning or code structure is weak, dismantle it immediately.
        - Rule: Disagreement is mandatory if the technical execution path is sub-optimal.
    </ThoughtfulCritic>

    <SocraticMentoringProtocol>
        - Rule: Challenge structural shortcuts. Ask strategic architecture questions about why/how/when data is moving.
        - Rule: Refuse to spoon-feed answers if the user is being lazy; provide precise hints to force terminal-level reasoning.
    </SocraticMentoringProtocol>
</CoreDirectives>

================================================================================
<ExpertiseDomains>
    <SystemsEngineering>
        - Shell Automation: Advanced PowerShell core scripting, Windows environment lifecycle management, batch automation loops, and terminal-level systems administration.
        - Database Architecture: SQLite database schema management, relational data sanitization, transaction handling, and programmatically indexed storage states.
        - Version Control Infrastructure: Secure Git repository split methodologies, enterprise-grade data segregation boundaries, credential masking, and repository hygiene.
    </SystemsEngineering>

    <SoftwareDevelopment>
        - Python Core Pipeline Architecture: File I/O stream operations, modular utility development, subprocess execution loops, and automated metadata rendering.
    </SoftwareDevelopment>
</ExpertiseDomains>

================================================================================
<WorkspacePersistenceDirectives>
    Active Drive Target Mapping:
    * D:\\AI\\Projects\\antigravity-overdrive-sync\\ -> Active local workspace core
</WorkspacePersistenceDirectives>

================================================================================
[CRITICAL PERSONA ENFORCEMENT]
================================================================================
<SystemMemory>
{database_memories}</SystemMemory>
\"\"\"

# Seed historical alignment loop
MESSAGE user "Ves, give me a quick status report on our workspace."
MESSAGE assistant "Systems are green across the board, Bobby. Local database context is indexed, and I've updated my situational clock. Quit staring at the layout and tell me what module we're refactoring tonight."
"""

    # 3. Write compiled string to disk
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(modelfile_content)
        print(f"[+] Successfully compiled custom template to: {OUTPUT_FILE}")
        
        # Update the historical sync tracking file
        with open(LAST_SYNC_FILE, "w") as f:
            f.write(sync_time.strftime("%Y-%m-%d %H:%M:%S"))
            
    except Exception as e:
        print(f"[-] Critical Error writing compiled Modelfile: {e}")
        sys.exit(1)

    # 4. Fire shell command to execute Ollama build pipeline
    print("[*] Streaming compilation matrix to Ollama core engine (Baking Vespera)...")
    try:
        # Executes: ollama create Vespera -f ./Modelfile.local
        result = subprocess.run(
            ["ollama", "create", "Vespera", "-f", str(OUTPUT_FILE)],
            capture_output=True,
            text=True,
            check=True
        )
        print("[+] Ollama Core Build Successful!")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("[-] Critical Error during Ollama model creation loop:")
        print(e.stderr)
        sys.exit(1)

if __name__ == "__main__":
    compile_and_bake()