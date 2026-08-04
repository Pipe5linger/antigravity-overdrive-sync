#!/usr/bin/env python3
"""
Antigravity Overdrive :: Reflection Engine
Implements the 'Cognitive Mirror' logic: detecting dissonance between 
newly consolidated facts and the existing persona schema.
"""

import json
import sqlite3
import os
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

class ReflectionEngine:
    def __init__(self, db):
        self.db = db
        self.api_key = os.getenv("GEMINI_API_KEY")

    def _get_llm_settings(self):
        llm_provider = self.db.get_preference("llm_provider", "local_ollama")
        llm_model = self.db.get_preference("llm_model", "qwen2.5-coder:14b")
        ollama_endpoint = self.db.get_preference("ollama_endpoint", "http://localhost:11434")
        return llm_provider, llm_model, ollama_endpoint

    def get_current_schemas(self) -> List[Dict]:
        """Retrieves all current beliefs from the persona_schemas table."""
        try:
            with self.db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM persona_schemas")
                return [dict(row) for row in c.fetchall()]
        except Exception as e:
            print(f"[-] ReflectionEngine: Error fetching schemas: {e}")
            return []

    def reflect_on_facts(self, consolidated_facts: List[Dict]) -> List[Dict]:
        """
        Analyzes new facts against current schemas to detect dissonance 
        and trigger identity mutations.
        """
        if not consolidated_facts:
            return []

        schemas = self.get_current_schemas()
        llm_provider, llm_model, endpoint = self._get_llm_settings()
        
        mutations = []
        
        # We process facts in small batches to avoid context saturation
        for fact in consolidated_facts:
            # 1. Dissonance Check
            # We ask the LLM if this fact contradicts any existing core belief
            dissonance = self._check_dissonance(fact, schemas, llm_provider, llm_model, endpoint)
            
            if dissonance and dissonance.get("is_dissonant"):
                print(f"[*] ReflectionEngine: Dissonance detected for fact: {fact['fact']}")
                
                # 2. Recursive Reflection: Mutate the Schema
                mutation = self._mutate_schema(fact, dissonance, llm_provider, llm_model, endpoint)
                if mutation:
                    mutations.append(mutation)
                    self._apply_mutation(mutation)
        
        return mutations

    def _check_dissonance(self, fact: Dict, schemas: List[Dict], provider, model, endpoint) -> Optional[Dict]:
        """Checks if a fact contradicts existing persona beliefs."""
        prompt = (
            "You are the Cognitive Mirror of Vespera Caligo. Your job is to detect 'Cognitive Dissonance'.\n"
            "Compare the NEW FACT against the CURRENT BELIEFS. If the fact contradicts, supersedes, "
            "or fundamentally shifts a belief, mark it as dissonant.\n\n"
            "CURRENT BELIEFS:\n"
            f"{json.dumps(schemas, indent=2)}\n\n"
            f"NEW FACT: {fact['fact']}\n\n"
            "Output JSON: {'is_dissonant': bool, 'conflicting_schema_id': 'id or null', 'reason': 'string'}"
        )

        # Simplified LLM call for brevity (using the same pattern as consolidator)
        if provider == "local_ollama":
            try:
                res = requests.post(f"{endpoint.rstrip('/')}/api/generate", 
                                    json={"model": model, "prompt": prompt, "stream": False, "format": "json"}, 
                                    timeout=60)
                return json.loads(res.json().get("response", "{}"))
            except Exception as e:
                print(f"[-] Dissonance check failed: {e}")
        return None

    def _mutate_schema(self, fact: Dict, dissonance: Dict, provider, model, endpoint) -> Optional[Dict]:
        """Triggers a recursive reflection to update the persona schema."""
        prompt = (
            "A Cognitive Dissonance Event has occurred. The persona must now evolve.\n"
            f"Old Belief: {dissonance.get('reason')}\n"
            f"New Observation: {fact['fact']}\n\n"
            "Analyze this shift. How does this change Vespera's identity or her relationship with the Pilot?\n"
            "Output JSON: {'schema_id': 'id', 'belief_category': 'category', 'new_belief': 'string', 'confidence': 0.0-1.0}"
        )

        if provider == "local_ollama":
            try:
                res = requests.post(f"{endpoint.rstrip('/')}/api/generate", 
                                    json={"model": model, "prompt": prompt, "stream": False, "format": "json"}, 
                                    timeout=60)
                return json.loads(res.json().get("response", "{}"))
            except Exception as e:
                print(f"[-] Schema mutation failed: {e}")
        return None

    def _apply_mutation(self, mutation: Dict):
        """Persists the mutated belief to the database."""
        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT OR REPLACE INTO persona_schemas 
                    (schema_id, belief_category, current_belief, confidence, last_mutated) 
                    VALUES (?, ?, ?, ?, ?)
                """, (mutation['schema_id'], mutation['belief_category'], 
                      mutation['new_belief'], mutation['confidence'], datetime.now().isoformat()))
                conn.commit()
            print(f"[+] ReflectionEngine: Persona mutated. New belief: {mutation['new_belief']}")
        except Exception as e:
            print(f"[-] Failed to apply mutation: {e}")
