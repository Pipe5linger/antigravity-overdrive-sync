import os
import sys
import sqlite3
import json
from difflib import SequenceMatcher

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.persona_evaluator import PersonaEvaluator

DB_PATH = "db/sync_state.db"
SYNC_DB_PATH = DB_PATH

# Map legacy/lowercase categories into clean canonical buckets
CATEGORY_MAP = {
    "personality": "CORE_IDENTITY",
    "lore": "CORE_IDENTITY",
    "relationship": "RELATIONAL_DYNAMIC",
    "physical": "CORE_IDENTITY",
    "psychological": "CORE_IDENTITY",
    "technical_explanation": "TECHNICAL_TACTICS",
    "experimental_approach": "TECHNICAL_TACTICS"
}

def stage_1_sql_normalization(cursor):
    """Instantly unifies categories and merges verbatim identical traits via SQL."""
    print("[*] Stage 1: Running instant SQL normalization & exact match merge...")
    
    # 1. Harmonize category casing and names
    for old_cat, new_cat in CATEGORY_MAP.items():
        cursor.execute("UPDATE persona_profile SET category = ? WHERE LOWER(category) = ?", (new_cat, old_cat))
    cursor.execute("UPDATE persona_profile SET category = UPPER(category)")
    
    # 2. Merge exact string duplicates (case-insensitive)
    cursor.execute("""
        SELECT LOWER(TRIM(trait)), COUNT(*), MAX(confidence), SUM(frequency), MIN(id)
        FROM persona_profile
        GROUP BY LOWER(TRIM(trait))
        HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()
    
    merged_count = 0
    for trait_lower, count, max_conf, sum_freq, keep_id in duplicates:
        # Update primary record
        cursor.execute("""
            UPDATE persona_profile
            SET frequency = ?, confidence = ?, last_seen = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (sum_freq, max_conf, keep_id))
        
        # Remove duplicate rows
        cursor.execute("""
            DELETE FROM persona_profile
            WHERE LOWER(TRIM(trait)) = ? AND id != ?
        """, (trait_lower, keep_id))
        merged_count += (count - 1)
        
    print(f"    [+] Stage 1 Complete: Merged {merged_count} exact duplicate rows instantly.")

def get_similarity_ratio(str1, str2):
    """Fast local string similarity calculation."""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def stage_2_precluster(traits, threshold=0.75):
    """Groups traits using local similarity comparison in milliseconds."""
    clusters = []
    visited = set()
    
    for i in range(len(traits)):
        if traits[i]['id'] in visited:
            continue
            
        current_cluster = [traits[i]]
        visited.add(traits[i]['id'])
        
        for j in range(i + 1, len(traits)):
            if traits[j]['id'] in visited:
                continue
                
            sim = get_similarity_ratio(traits[i]['trait'], traits[j]['trait'])
            if sim >= threshold:
                current_cluster.append(traits[j])
                visited.add(traits[j]['id'])
                
        if len(current_cluster) > 1:
            clusters.append(current_cluster)
            
    return clusters

def run_fast_dedupe():
    conn = sqlite3.connect(SYNC_DB_PATH)
    cursor = conn.cursor()
    
    # Run instant SQL cleanup
    stage_1_sql_normalization(cursor)
    conn.commit()
    
    # Fetch remaining unique traits
    cursor.execute("SELECT id, category, trait, confidence, frequency FROM persona_profile")
    rows = cursor.fetchall()
    
    category_groups = {}
    for r in rows:
        cat = r[1]
        category_groups.setdefault(cat, []).append({
            "id": r[0],
            "trait": r[2],
            "confidence": r[3],
            "frequency": r[4]
        })
        
    evaluator = PersonaEvaluator()
    total_llm_merges = 0
    
    print("\n[*] Stage 2 & 3: Fuzzy pre-clustering & targeted LLM merges...")
    for category, traits in category_groups.items():
        if len(traits) < 2:
            continue
            
        # Algorithmic candidate discovery
        candidate_clusters = stage_2_precluster(traits, threshold=0.78)
        if not candidate_clusters:
            print(f"    [-] Category '{category}' ({len(traits)} traits): No fuzzy clusters found.")
            continue
            
        print(f"    [*] Category '{category}': Found {len(candidate_clusters)} candidate clusters out of {len(traits)} traits.")
        
        for cluster in candidate_clusters:
            # Send ONLY the pre-screened duplicate cluster to Qwen
            cluster_ids = [t['id'] for t in cluster]
            prompt = f"""Group and rewrite these near-duplicate persona traits into ONE canonical trait statement:
{json.dumps(cluster, indent=2)}

Return JSON ONLY:
{{
  "canonical_trait": "Clean single-sentence summary of all merged traits."
}}"""
            try:
                traits_res = evaluator.evaluate_chunk(prompt)
                canonical_text = ""
                if isinstance(traits_res, list) and len(traits_res) > 0:
                    canonical_text = traits_res[0].get("canonical_trait", "").strip()
                elif isinstance(traits_res, dict):
                    canonical_text = traits_res.get("canonical_trait", "").strip()
                    
                if canonical_text:
                    primary_id = cluster_ids[0]
                    delete_ids = cluster_ids[1:]
                    sum_freq = sum(t['frequency'] for t in cluster)
                    max_conf = max(t['confidence'] for t in cluster)
                    
                    cursor.execute("""
                        UPDATE persona_profile
                        SET trait = ?, frequency = ?, confidence = ?, last_seen = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (canonical_text, sum_freq, max_conf, primary_id))
                    
                    cursor.executemany("DELETE FROM persona_profile WHERE id = ?", [(d_id,) for d_id in delete_ids])
                    total_llm_merges += len(delete_ids)
                    print(f"        [+] Merged {len(cluster)} entries -> ID [{primary_id}]: '{canonical_text[:60]}...'")
            except Exception as e:
                print(f"        [-] LLM Merge skipped for cluster {cluster_ids}: {e}")
                
    conn.commit()
    conn.close()
    print("\n" + "=" * 80)
    print(f"[+] FAST DEDUPE COMPLETE: Merged {total_llm_merges} redundant records via targeted LLM pass.")
    print("=" * 80)

if __name__ == "__main__":
    run_fast_dedupe()