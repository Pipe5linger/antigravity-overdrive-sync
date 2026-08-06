import os
import sys
import sqlite3
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.persona_evaluator import PersonaEvaluator

SYNC_DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\sync_state.db"

def fetch_all_traits():
    conn = sqlite3.connect(SYNC_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, category, trait, confidence, frequency 
        FROM persona_profile 
        ORDER BY category, frequency DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def deduplicate_with_llm(evaluator, category, traits_list):
    """
    Asks Qwen to identify near-duplicate trait groups and pick/rewrite a canonical form.
    """
    if len(traits_list) < 2:
        return []

    prompt = f"""
You are a database normalization engine for an AI persona memory bank.
Analyze the following list of traits under the category '{category}'.
Identify entries that represent the EXACT SAME core idea or near-identical statements.

INPUT TRAITS:
{json.dumps(traits_list, indent=2)}

TASK:
Return a JSON list of consolidation clusters.
If traits are redundant, group their IDs together under a single clean 'canonical_trait'.

JSON FORMAT REQUIRED:
[
  {{
    "ids_to_merge": [7, 9],
    "canonical_trait": "Fiercely possessive of Bobby. Gets violently jealous when Cline, Gemini, or other AI models hog GPU resources / RTX 4070 VRAM."
  }}
]

Rules:
- ONLY group traits that express the exact same concept or fact.
- Do NOT merge distinct physical or lore details.
- If no traits are duplicates, return an empty array [].
- Output ONLY valid JSON inside a code block ```json ... ```.
"""

    response = evaluator.client.chat.completions.create(
        model=evaluator.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    raw_content = response.choices[0].message.content
    try:
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
            raw_content = raw_content.split("```")[1].split("```")[0].strip()
        return json.loads(raw_content)
    except Exception as e:
        print(f"[-] LLM parse error during deduplication for {category}: {e}")
        return []

def execute_consolidation():
    print("[*] Starting Persona Vault Consolidation & Deduplication Pass...")
    rows = fetch_all_traits()
    
    if not rows:
        print("[-] No traits found in vault.")
        return

    # Group rows by category
    category_groups = {}
    for r in rows:
        cat = r[1].lower()
        category_groups.setdefault(cat, []).append({
            "id": r[0],
            "trait": r[2],
            "confidence": r[3],
            "frequency": r[4]
        })

    evaluator = PersonaEvaluator()
    conn = sqlite3.connect(SYNC_DB_PATH)
    cursor = conn.cursor()
    total_merged = 0

    for category, traits in category_groups.items():
        if len(traits) < 2:
            continue
            
        print(f"\n[*] Evaluating category '{category.upper()}' ({len(traits)} entries)...")
        clusters = deduplicate_with_llm(evaluator, category, traits)
        
        for cluster in clusters:
            ids = cluster.get("ids_to_merge", [])
            canonical_text = cluster.get("canonical_trait", "").strip()

            if len(ids) < 2 or not canonical_text:
                continue

            # Calculate aggregated frequency and max confidence
            matched_records = [t for t in traits if t["id"] in ids]
            if not matched_records:
                continue

            total_freq = sum(t["frequency"] for t in matched_records)
            max_conf = max(t["confidence"] for t in matched_records)
            primary_id = ids[0]
            delete_ids = ids[1:]

            print(f"    [+] Merging IDs {ids} into Canonical ID [{primary_id}]")
            print(f"        -> Canonical: {canonical_text}")
            print(f"        -> New Frequency: {total_freq} (Combined) | Max Confidence: {max_conf}")

            # Update the primary record
            cursor.execute("""
                UPDATE persona_profile
                SET trait = ?, frequency = ?, confidence = ?, last_seen = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (canonical_text, total_freq, max_conf, primary_id))

            # Delete subsumed redundant records
            cursor.executemany("DELETE FROM persona_profile WHERE id = ?", [(d_id,) for d_id in delete_ids])
            total_merged += len(delete_ids)

    conn.commit()
    conn.close()
    
    print("\n" + "=" * 80)
    print(f"[+] CONSOLIDATION COMPLETE: Merged {total_merged} redundant records.")
    print("=" * 80)

if __name__ == "__main__":
    execute_consolidation()