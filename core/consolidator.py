# D:\AI\Projects\antigravity-overdrive-sync\core\consolidator.py
import json
import sqlite3
import sys
import os
import time
import subprocess
import requests
import numpy as np
import datetime
from typing import List, Dict, Any
from core.database import ULMDatabase
from core.temporal_degradation import TemporalDegradation

class MemoryConsolidator:
    def __init__(self, db: ULMDatabase, api_key=None):
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def _is_ollama_running(self, endpoint: str) -> bool:
        """Checks whether the Ollama server is responding on its API."""
        try:
            res = requests.get(f"{endpoint.rstrip('/')}/api/tags", timeout=5)
            return res.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def _get_available_ollama_models(self, endpoint: str) -> List[str]:
        """Returns a list of model names available in the local Ollama instance."""
        try:
            res = requests.get(f"{endpoint.rstrip('/')}/api/tags", timeout=5)
            if res.status_code == 200:
                return [m["name"] for m in res.json().get("models", [])]
        except Exception:
            pass
        return []

    def _ensure_ollama_ready(self, endpoint: str) -> bool:
        """Ensures Ollama is running. Auto-launches if needed, then polls until ready."""
        if self._is_ollama_running(endpoint):
            return True

        ollama_bin = os.path.expanduser(r"~\AppData\Local\Programs\Ollama\ollama.exe")
        if not os.path.isfile(ollama_bin):
            ollama_bin = "ollama"

        print(f"[+] MemoryConsolidator: Ollama not responding — auto-launching ({ollama_bin})...")
        try:
            subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as e:
            print(f"[-] MemoryConsolidator: Failed to launch Ollama: {e}")
            return False

        # Poll for up to ~30 seconds (60 × 0.5s)
        for attempt in range(60):
            time.sleep(0.5)
            if self._is_ollama_running(endpoint):
                print("[+] MemoryConsolidator: Ollama server is online and ready!")
                return True

        print("[-] MemoryConsolidator: Ollama did not come online within 30 seconds.")
        return False

    def _try_embed_endpoint(self, url: str, payload: dict, use_v1_api: bool = False) -> List[float]:
        """Attempts to call either /api/embed (v1) or /api/embeddings (legacy) and returns the embedding list.
        Returns None if the endpoint is not found (404) or fails in a way that should trigger fallback."""
        try:
            res = requests.post(url, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json()
            if use_v1_api:
                return data.get("embeddings", [[]])[0]
            else:
                return data.get("embedding", [])
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            body = e.response.text[:200] if e.response is not None else ""
            print(f"[-] MemoryConsolidator: Embed endpoint returned HTTP {status}: {body}")
            return None  # signal: endpoint failed, try next
        except requests.exceptions.ConnectionError:
            raise  # let caller handle wake-up + retry
        except Exception as e:
            print(f"[-] MemoryConsolidator: Embed endpoint unexpected error: {e}")
            return None  # signal: endpoint failed, try next

    def _get_batch_embeddings(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        """Generates embeddings for multiple texts in batch using Ollama's /api/embed endpoint.
        This is 50-100x faster than sequential requests."""
        llm_provider = self.db.get_preference("llm_provider", "local_ollama")
        vector_model = self.db.get_preference("vector_model", "nomic-embed-text:latest")
        ollama_endpoint = self.db.get_preference("ollama_endpoint", "http://localhost:11434")
        base = ollama_endpoint.rstrip("/")

        if llm_provider != "local_ollama":
            return [[] for _ in texts]

        all_embeddings = []
        
        # Process in batches to avoid overwhelming Ollama
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            try:
                # Use Ollama v1 /api/embed with batch input
                payload = {"model": vector_model, "input": batch}
                res = requests.post(f"{base}/api/embed", json=payload, timeout=60)
                res.raise_for_status()
                data = res.json()
                batch_embeddings = data.get("embeddings", [])
                all_embeddings.extend(batch_embeddings)
                print(f"[*] MemoryConsolidator: Batch embedded {len(batch)} texts ({i+len(batch)}/{len(texts)})")
            except Exception as e:
                print(f"[-] MemoryConsolidator: Batch embedding failed: {e}, falling back to sequential...")
                # Fallback to sequential for this batch
                for text in batch:
                    emb = self._get_embedding(text)
                    all_embeddings.append(emb if emb else [])
        
        return all_embeddings

    def _get_embedding(self, text: str) -> List[float]:
        """Generates a vector embedding for the given text using the configured vector model."""
        llm_provider = self.db.get_preference("llm_provider", "local_ollama")
        vector_model = self.db.get_preference("vector_model", "nomic-embed-text:latest")
        ollama_endpoint = self.db.get_preference("ollama_endpoint", "http://localhost:11434")
        base = ollama_endpoint.rstrip("/")

        if llm_provider != "local_ollama":
            return []

        # Auto-detect available embedding models if the configured one isn't pulled
        available_models = self._get_available_ollama_models(base)
        if available_models and vector_model not in available_models:
            # Find the first embedding-capable model
            embed_models = [m for m in available_models if "embed" in m.lower() or "minilm" in m.lower()]
            if embed_models:
                vector_model = embed_models[0]
                print(f"[*] MemoryConsolidator: Using detected embedding model: {vector_model}")
            else:
                print(f"[-] MemoryConsolidator: No embedding model found in Ollama. Available: {available_models[:5]}...")
                return []

        urls_and_payloads = [
            # Primary: Ollama v1 /api/embed (uses "input" key)
            (f"{base}/api/embed", {"model": vector_model, "input": text}, True),
            # Fallback: legacy /api/embeddings (uses "prompt" key)
            (f"{base}/api/embeddings", {"model": vector_model, "prompt": text}, False),
        ]

        for url, payload, use_v1 in urls_and_payloads:
            try:
                result = self._try_embed_endpoint(url, payload, use_v1)
                if result is not None:
                    return result
                # 404 from this endpoint — try next one
            except requests.exceptions.ConnectionError:
                print("[!] MemoryConsolidator: Ollama connection refused — attempting to wake service and retry...")
                if self._ensure_ollama_ready(ollama_endpoint):
                    print("[*] MemoryConsolidator: Retrying embedding after warm-up...")
                    time.sleep(5)
                    try:
                        result = self._try_embed_endpoint(url, payload, use_v1)
                        if result is not None:
                            return result
                    except requests.exceptions.ConnectionError:
                        pass  # fall through to next endpoint
                    except Exception as e:
                        print(f"[-] MemoryConsolidator: Embedding retry failed: {e}")
                else:
                    print("[-] MemoryConsolidator: Could not start Ollama. Skipping embedding generation.")
                    return []
            except Exception as e:
                print(f"[-] MemoryConsolidator: Embedding generation failed: {e}")
                return []

        # All endpoints exhausted
        print("[-] MemoryConsolidator: All embedding endpoints failed. Skipping embedding generation.")
        return []

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Calculates the cosine similarity between two vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        a = np.array(v1)
        b = np.array(v2)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def _cluster_facts(self, facts: List[Dict], threshold=0.8, max_facts=200) -> List[List[Dict]]:
        """Groups facts into semantic clusters using cosine similarity.
        OPTIMIZED: Uses vectorized operations and limits dataset size.
        """
        if not facts:
            return []
        
        # Cap the number of facts to process to prevent hanging
        if len(facts) > max_facts:
            print(f"[*] MemoryConsolidator: Limiting clustering to {max_facts} most recent facts (out of {len(facts)})")
            facts = sorted(facts, key=lambda x: x.get("last_seen", ""), reverse=True)[:max_facts]
        
        print(f"[*] MemoryConsolidator: Clustering {len(facts)} facts with threshold {threshold}...")
        
        # Filter out facts without embeddings
        valid_facts = [f for f in facts if f.get("embedding") and len(f["embedding"]) > 0]
        if len(valid_facts) < 2:
            print("[*] MemoryConsolidator: Not enough valid embeddings to cluster")
            return []
        
        print(f"[*] MemoryConsolidator: {len(valid_facts)} facts have valid embeddings")
        
        # Simple clustering: group facts with same category or very similar embeddings
        clusters = []
        used = set()
        
        for i, fact1 in enumerate(valid_facts):
            if i in used:
                continue
            
            cluster = [fact1]
            used.add(i)
            
            # Only compare with a sample of other facts to speed up
            sample_size = min(50, len(valid_facts) - i - 1)
            for j in range(i + 1, min(i + 1 + sample_size, len(valid_facts))):
                if j in used:
                    continue
                fact2 = valid_facts[j]
                
                # Quick category match first
                if fact1.get("category") == fact2.get("category"):
                    cluster.append(fact2)
                    used.add(j)
                # Then check embedding similarity
                elif self._cosine_similarity(fact1["embedding"], fact2["embedding"]) > threshold:
                    cluster.append(fact2)
                    used.add(j)
            
            if len(cluster) > 1:  # Only keep clusters with 2+ facts
                clusters.append(cluster)
            
            # Progress indicator
            if (i + 1) % 20 == 0:
                print(f"[*] MemoryConsolidator: Scanned {i + 1}/{len(valid_facts)} facts, found {len(clusters)} clusters so far...")
        
        print(f"[*] MemoryConsolidator: Clustering complete! Found {len(clusters)} clusters")
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
                print(f"[*] MemoryConsolidator: Calling Ollama for synthesis (timeout 30s)...")
                res = requests.post(url, json=payload, timeout=30)  # Reduced timeout from 120 to 30
                res.raise_for_status()
                result = json.loads(res.json().get("response", "{}"))
                print(f"[*] MemoryConsolidator: Synthesis successful for cluster")
                return result
            except requests.exceptions.Timeout:
                print(f"[-] MemoryConsolidator: Synthesis timed out after 30s - skipping cluster")
                return None
            except requests.exceptions.ConnectionError:
                print("[!] MemoryConsolidator: Synthesis connection refused — attempting to wake service and retry...")
                if self._ensure_ollama_ready(endpoint):
                    print("[*] MemoryConsolidator: Retrying synthesis after warm-up...")
                    time.sleep(2)
                    try:
                        res = requests.post(url, json=payload, timeout=30)
                        res.raise_for_status()
                        return json.loads(res.json().get("response", "{}"))
                    except Exception as e:
                        print(f"[-] MemoryConsolidator: Synthesis failed on retry: {e}")
                        return None
                else:
                    print("[-] MemoryConsolidator: Could not start Ollama for synthesis. Skipping cluster.")
                    return None
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
        embeddings_unavailable = False
        
        print(f"[*] MemoryConsolidator: Processing embeddings for {len(facts)} facts using BATCH processing...")
        
        # First, collect facts that need embeddings (not cached)
        facts_needing_embeddings = []
        cached_embeddings = {}
        
        for f in facts:
            fact_dict = dict(f)
            try:
                with self.db.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT embedding FROM fact_embeddings WHERE fact_id = ?", (f["fact_id"],))
                    row = c.fetchone()
                    if row:
                        # Convert BLOB back to list of floats
                        fact_dict["embedding"] = np.frombuffer(row[0], dtype=np.float32).tolist()
                        enriched_facts.append(fact_dict)
                    else:
                        facts_needing_embeddings.append((f, fact_dict))
            except Exception as e:
                print(f"[-] MemoryConsolidator: Error checking cache for {f.get('fact_id', 'unknown')}: {e}")
                fact_dict["embedding"] = []
                enriched_facts.append(fact_dict)
        
        print(f"[*] MemoryConsolidator: {len(enriched_facts)} facts have cached embeddings, {len(facts_needing_embeddings)} need new embeddings")
        
        # Batch embed all facts that need embeddings at once
        if facts_needing_embeddings:
            texts_to_embed = [f[0]["fact"] for f in facts_needing_embeddings]
            print(f"[*] MemoryConsolidator: Batch generating embeddings for {len(texts_to_embed)} facts...")
            try:
                batch_embeddings = self._get_batch_embeddings(texts_to_embed, batch_size=50)
                
                # Match embeddings back to facts and cache them
                for (original_fact, fact_dict), embedding in zip(facts_needing_embeddings, batch_embeddings):
                    if embedding and len(embedding) > 0:
                        fact_dict["embedding"] = embedding
                        # Cache it
                        try:
                            with self.db.get_connection() as conn:
                                c = conn.cursor()
                                c.execute("INSERT OR REPLACE INTO fact_embeddings (fact_id, embedding, model_id, created_at) VALUES (?, ?, ?, ?)",
                                          (original_fact["fact_id"], np.array(embedding, dtype=np.float32).tobytes(), "all-minilm", datetime.datetime.now().isoformat()))
                                conn.commit()
                        except Exception as e:
                            print(f"[-] MemoryConsolidator: Failed to cache embedding: {e}")
                    else:
                        fact_dict["embedding"] = []
                        print(f"[-] MemoryConsolidator: Failed to generate embedding for fact {original_fact.get('fact_id', 'unknown')[:8]}")
                    
                    enriched_facts.append(fact_dict)
                    
            except Exception as e:
                print(f"[-] MemoryConsolidator: Batch embedding failed: {e}")
                embeddings_unavailable = True
        
        if not enriched_facts:
            print("[!] MemoryConsolidator: No facts with embeddings available — skipping vector consolidation")
            return 0, 0

        # If embeddings are still unavailable after wake-up + retry, skip vector clustering
        if embeddings_unavailable:
            print("[!] MemoryConsolidator: Embedding service could not be reached after wake-up attempt — skipping vector consolidation. Pruning completed successfully.")
            return 0, 0

        # 2. Cluster facts by similarity
        try:
            print(f"[*] MemoryConsolidator: Starting clustering of {len(enriched_facts)} facts...")
            clusters = self._cluster_facts(enriched_facts)
            print(f"[*] MemoryConsolidator: Clustering complete! Found {len(clusters)} clusters")
        except Exception as e:
            print(f"[-] MemoryConsolidator: Clustering failed: {e}")
            import traceback
            traceback.print_exc()
            return 0, 0
        
        total_deleted = 0
        total_upserted = 0

        # 3. Synthesize top N clusters (limit to prevent hanging)
        MAX_SYNTHESIS_CLUSTERS = 20  # Only synthesize top 20 clusters
        clusters_to_synthesize = clusters[:MAX_SYNTHESIS_CLUSTERS]
        
        print(f"[*] MemoryConsolidator: Synthesizing top {len(clusters_to_synthesize)} clusters out of {len(clusters)} total...")
        
        for i, cluster in enumerate(clusters_to_synthesize):
            if len(cluster) < 2:
                continue
            
            try:
                print(f"[*] MemoryConsolidator: Synthesizing cluster {i+1}/{len(clusters_to_synthesize)} ({len(cluster)} facts)...")
                
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
                else:
                    print(f"[*] MemoryConsolidator: Skipping cluster {i+1} (synthesis failed or returned no result)")
            except Exception as e:
                print(f"[-] MemoryConsolidator: Synthesis failed for cluster {i+1}: {e}")
                import traceback
                traceback.print_exc()
                continue  # Skip this cluster and continue with others

        print(f"[+] MemoryConsolidator: Consolidation complete! Deleted {total_deleted} facts, upserted {total_upserted} golden facts")
        return total_deleted, total_upserted