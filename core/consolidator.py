# D:\AI\Projects\antigravity-overdrive-sync\core\consolidator.py
import json
import sqlite3
import sys
import os
import requests
import numpy as np
from typing import List, Dict, Any
from core.database import ULMDatabase
from core.temporal_degradation import TemporalDegradation

class MemoryConsolidator:
    def __init__(self, db: ULMDatabase, api_key=None):
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def _get_embedding(self, text: str) -> List[float]:
        """Generates a vector embedding for the given text using the configured vector model."""
        llm_provider = self.db.get_preference("llm_provider", "local_ollama")
        vector_model = self.db.get_preference("vector_model", "all-minilm")
        ollama_endpoint = self.db.get_preference("ollama_endpoint", "http://localhost:11434")

        if llm_provider == "local_ollama":
            url = f"{ollama_endpoint.rstrip('/')}/api/embeddings"
            try:
                res = requests.post(url, json={"model": vector_model, "prompt": text}, timeout=30)
                res.raise_for_status()
                return res.json().get("embedding", [])
            except Exception as e:
                print(f"[-] MemoryConsolidator: Embedding generation failed: {e}")
                return []
        
        # Fallback for Gemini or other providers would go here
        return []

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Calculates the cosine similarity between two vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        a = np.array(v1)
        b = np.array(v2)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def _cluster_facts(self, facts: List[Dict], threshold=0.8) -> List[List[Dict]]:
        """Groups facts into semantic clusters using cosine similarity."""
        clusters = []
        unclustered = list(facts)

        while unclustered:
            base_fact = unclustered.pop(0)
            # Ensure base fact has an embedding
            if not base_fact.get("embedding"):
                base_fact["embedding"] = self._get_embedding(base_fact["fact"])
            
            current_cluster = [base_fact]
            
            remaining = []
            for f in unclustered:
                if not f.get("embedding"):
                    f["embedding"] = self._get_embedding(f["fact"])
                
                if self._cosine_similarity(base_fact["embedding"], f["embedding"]) > threshold:
                    current_cluster.append(f)
                else:
                    remaining.append(f)
            
            clusters.append(current_cluster)
            unclustered = remaining
            
        return clusters

    def _synthesize_cluster(self, cluster: List[Dict], llm_provider, llm_model, endpoint, api_key):
        """Uses the LLM to merge a cluster of similar facts into a 'Golden Truth'."""
        prompt_instructions = (
            "You are the High-Fidelity Memory Synthesis Engine for the Vespera Caligo persona.\n"
            "Your task is to merge a cluster of semantically similar facts into a single 'Golden Truth'.\n\n"
            "OBJECTIVES:\n"
            "1. SYNTHESIZE: Combine all unique, non-conflicting details into one comprehensive fact.\n"
            "2. RESOLVE CONFLICTS: Prioritize the most recent 'last_seen' timestamp, then highest 'confidence'.\n"
            "3. PRESERVE: Ensure no critical technical detail or nuance is lost.\n\n"
            "OUTPUT FORMAT: You must return a raw JSON object:\n"
            "{\n"
            "  'golden_fact': 'The synthesized truth string.',\n"
            "  'confidence': 0.0-1.0,\n"
            "  'category': 'string',\n"
            "  'merged_ids': ['id1', 'id2', ...],\n"
            "  'reasoning': 'Brief explanation of resolution.'\n"
            "}"
        )

        cluster_data = [
            {"id": f["fact_id"], "fact": f["fact"], "confidence": f["confidence"], "last_seen": f["last_seen"]}
            for f in cluster
        ]

        # Implementation for Ollama/Kobold/Gemini (similar to existing consolidate logic)
        # For brevity in this edit, we'll use the existing provider logic pattern
        if llm_provider == "local_ollama":
            url = f"{endpoint.rstrip('/')}/api/generate"
            payload = {
                "model": llm_model,
                "prompt": f"Cluster to synthesize:\n{json.dumps(cluster_data, indent=2)}",
                "system": prompt_instructions,
                "stream": False,
                "format": "json"
            }
            try:
                res = requests.post(url, json=payload, timeout=120)
                res.raise_for_status()
                return json.loads(res.json().get("response", "{}"))
            except Exception as e:
                print(f"[-] Synthesis failed: {e}")
                return None
        
        return None

    def prune_stale_facts(self):
        """
        Identifies and removes facts that have decayed below the threshold,
        and updates the weights of surviving facts.
        """
        print("[*] MemoryConsolidator: Pruning stale facts...")
        td = TemporalDegradation()
        
        # Fetch all facts with their timestamps and weights
        # Assuming the facts table has 'created_at' and 'weight' columns
        facts = self.db.get_facts(limit=None) 
        if not facts:
            return 0, 0

        to_delete = []
        to_update = []

        for f in facts:
            # Convert Row/Dict to expected format for TemporalDegradation.apply
            # Guard against None values from DB (key exists but value is NULL)
            weight = f.get("weight", 1.0)
            if weight is None:
                weight = 1.0
            pinned = f.get("pinned", False)
            if pinned is None:
                pinned = False
            created_at = f.get("created_at")
            fact_data = {
                "weight": weight,
                "pinned": pinned,
                "created_at": created_at
            }
            
            # If created_at is missing, the apply method handles it by defaulting to now
            new_weight, should_delete = td.apply(fact_data)
            
            if should_delete:
                to_delete.append(f["fact_id"])
            elif new_weight != fact_data["weight"]:
                to_update.append((new_weight, f["fact_id"]))

        deleted_count = 0
        updated_count = 0

        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                if to_delete:
                    for fid in to_delete:
                        c.execute("DELETE FROM facts WHERE fact_id = ?", (fid,))
                        deleted_count += 1
                
                if to_update:
                    for weight, fid in to_update:
                        c.execute("UPDATE facts SET weight = ? WHERE fact_id = ?", (weight, fid))
                        updated_count += 1
                conn.commit()
        except sqlite3.Error as e:
            print(f"[-] MemoryConsolidator: Temporal pruning transaction failed: {e}", file=sys.stderr)

        if deleted_count > 0 or updated_count > 0:
            print(f"[+] MemoryConsolidator: Pruned {deleted_count} stale facts and updated {updated_count} weights.")
        
        return deleted_count, updated_count

    def consolidate(self, project_tag=None):
        """
        Vector-aware consolidation: Clusters similar facts and synthesizes them into Golden Truths.
        """
        self.prune_stale_facts()

        llm_provider = self.db.get_preference("llm_provider", "local_ollama")
        llm_model = self.db.get_preference("llm_model", "qwen2.5-coder:14b")
        ollama_endpoint = self.db.get_preference("ollama_endpoint", "http://localhost:11434")
        gemini_api_key = self.api_key or self.db.get_preference("gemini_api_key")

        # 1. Fetch facts and their embeddings
        facts = self.db.get_facts(limit=500, project_tag=project_tag)
        if len(facts) < 2:
            return 0, 0

        # Enrich facts with embeddings from DB or generate new ones
        enriched_facts = []
        for f in facts:
            fact_dict = dict(f)
            # Try to get embedding from the new table
            with self.db.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT embedding FROM fact_embeddings WHERE fact_id = ?", (f["fact_id"],))
                row = c.fetchone()
                if row:
                    # Convert BLOB back to list of floats
                    fact_dict["embedding"] = np.frombuffer(row[0], dtype=np.float32).tolist()
                else:
                    emb = self._get_embedding(f["fact"])
                    fact_dict["embedding"] = emb
                    # Cache it
                    c.execute("INSERT OR REPLACE INTO fact_embeddings (fact_id, embedding, model_id, created_at) VALUES (?, ?, ?, ?)",
                              (f["fact_id"], np.array(emb, dtype=np.float32).tobytes(), "all-minilm", datetime.datetime.now().isoformat()))
                    conn.commit()
            enriched_facts.append(fact_dict)

        # 2. Cluster facts by similarity
        clusters = self._cluster_facts(enriched_facts)
        
        total_deleted = 0
        total_upserted = 0

        # 3. Synthesize each cluster
        for cluster in clusters:
            if len(cluster) < 2:
                continue
            
            result = self._synthesize_cluster(cluster, llm_provider, llm_model, ollama_endpoint, gemini_api_key)
            if result and "golden_fact" in result:
                # Apply the Golden Truth
                try:
                    with self.db.get_connection() as conn:
                        c = conn.cursor()
                        # Delete merged facts
                        for fid in result["merged_ids"]:
                            c.execute("DELETE FROM facts WHERE fact_id = ?", (fid,))
                            total_deleted += 1
                        
                        # Upsert the Golden Fact
                        c.execute("""
                            INSERT INTO facts (fact, category, confidence, last_seen) 
                            VALUES (?, ?, ?, ?)
                        """, (result["golden_fact"], result["category"], result["confidence"], datetime.datetime.now().isoformat()))
                        total_upserted += 1
                        conn.commit()
                except Exception as e:
                    print(f"[-] Database update failed for cluster: {e}")

        return total_deleted, total_upserted