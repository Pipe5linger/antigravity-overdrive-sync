import json
import sqlite3
import sys
import os
import requests
import urllib.request
import urllib.error
from core.database import ULMDatabase

class MemoryConsolidator:
    def __init__(self, db: ULMDatabase, api_key=None):
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def consolidate(self, project_tag=None):
        """
        Retrieves facts, detects contradictions/redundancies via LLM,
        and applies corrections (deletions and upserts) to the database.
        """
        # 1. Fetch LLM settings from preferences
        llm_provider = self.db.get_preference("llm_provider", "local_ollama")
        llm_model = self.db.get_preference("llm_model", "qwen2.5-coder:14b")
        ollama_endpoint = self.db.get_preference("ollama_endpoint", "http://localhost:11434")
        gemini_api_key = self.api_key or self.db.get_preference("gemini_api_key")

        # 2. Get all facts (or filter by project_tag if wanted, but global consolidation is better to see cross-project conflicts)
        facts = self.db.get_facts(limit=200, project_tag=None)
        if len(facts) < 2:
            # Not enough facts to consolidate
            return 0, 0

        # Format facts for the LLM prompt
        formatted_facts = []
        for f in facts:
            formatted_facts.append({
                "fact_id": f["fact_id"],
                "fact": f["fact"],
                "category": f["category"],
                "confidence": f["confidence"],
                "project_tag": f["project_tag"],
                "last_seen": f["last_seen"]
            })

        prompt_instructions = (
            "You are a memory consolidation and conflict resolution engine.\n"
            "Analyze the following list of developer facts and identify:\n"
            "1. Contradictions: Facts that directly negate or conflict with each other (e.g., 'Pilot prefers poetry' vs 'Pilot prefers pipenv'). Keep the newer or more accurate fact, or merge them. Mark the obsolete/incorrect ones for deletion.\n"
            "2. Redundancy/Duplicates: Facts that convey the same information in different words (e.g., 'User works on Windows' and 'Developer's operating system is Windows'). Refine them into a single, high-quality consolidated fact, delete the duplicates, and add the consolidated fact.\n"
            "3. Obsolescence: Facts that have been superseded by more recent information.\n\n"
            "Your output MUST be a JSON object with two fields:\n"
            "- 'deletions': A list of string fact_ids that should be removed because they are obsolete, redundant, or incorrect.\n"
            "- 'upserts': A list of objects representing new or updated facts. Each object must have:\n"
            "  * 'fact': The text of the consolidated/updated fact.\n"
            "  * 'category': The category (e.g., 'technical', 'persona', etc.).\n"
            "  * 'confidence': Float confidence score (0.1 to 1.0).\n"
            "  * 'project_tag': The project tag (string or null).\n\n"
            "Be precise. Only delete or modify facts if there is clear redundancy, contradiction, or obsolescence. Do not invent new facts."
        )

        input_payload = {
            "facts": formatted_facts
        }

        raw_result = None
        if llm_provider == "local_ollama":
            url = f"{ollama_endpoint.rstrip('/')}/api/generate"
            payload = {
                "model": llm_model,
                "prompt": f"Facts to consolidate:\n{json.dumps(input_payload, indent=2)}",
                "system": prompt_instructions,
                "stream": False,
                "format": "json"
            }
            try:
                response = requests.post(url, json=payload, timeout=120)
                response.raise_for_status()
                raw_result = response.json().get("response", "{}").strip()
            except Exception as e:
                print(f"[-] MemoryConsolidator: Ollama consolidation failed: {e}", file=sys.stderr)
                return 0, 0
        elif llm_provider == "cloud_gemini":
            if not gemini_api_key:
                print("[-] MemoryConsolidator: Gemini key not configured.", file=sys.stderr)
                return 0, 0
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={gemini_api_key}"
            payload = {
                "contents": [{
                    "parts": [{"text": f"{prompt_instructions}\n\nFacts:\n{json.dumps(input_payload, indent=2)}"}]
                }],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=90) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    raw_result = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            except Exception as e:
                print(f"[-] MemoryConsolidator: Gemini consolidation failed: {e}", file=sys.stderr)
                return 0, 0
        else:
            print(f"[-] MemoryConsolidator: Unknown provider: {llm_provider}", file=sys.stderr)
            return 0, 0

        if not raw_result:
            return 0, 0

        try:
            consolidation_plan = json.loads(raw_result)
            if isinstance(consolidation_plan, str):
                consolidation_plan = json.loads(consolidation_plan)
        except Exception as e:
            print(f"[-] MemoryConsolidator: Error parsing JSON output: {e}\nRaw: {raw_result}", file=sys.stderr)
            return 0, 0

        deletions = consolidation_plan.get("deletions", [])
        upserts = consolidation_plan.get("upserts", [])

        # Apply deletions and upserts to the database
        deleted_count = 0
        upserted_count = 0

        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                if deletions:
                    for fact_id in deletions:
                        c.execute("DELETE FROM facts WHERE fact_id = ?", (fact_id,))
                        deleted_count += 1
                
                if upserts:
                    for item in upserts:
                        fact_text = item.get("fact")
                        cat = item.get("category", "technical")
                        conf = item.get("confidence", 0.8)
                        tag = item.get("project_tag")
                        if fact_text:
                            self.db.upsert_fact(fact=fact_text, category=cat, confidence=conf, project_tag=tag, conn=conn)
                            upserted_count += 1
                conn.commit()
        except sqlite3.Error as e:
            print(f"[-] MemoryConsolidator: Database transaction failed: {e}", file=sys.stderr)
            return 0, 0

        if deleted_count > 0 or upserted_count > 0:
            print(f"[+] MemoryConsolidator: Consolidated facts. Removed {deleted_count} obsolete/contradictory facts, applied {upserted_count} upserts.")
        return deleted_count, upserted_count
