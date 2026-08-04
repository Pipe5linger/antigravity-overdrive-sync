# D:\AI\Projects\antigravity-overdrive-sync\core\profile_evaluator.py
import os
import sys
import json
import asyncio
import httpx
import sqlite3
from core.utils import AsyncTokenBucket
from core.fact_extractor import FactExtractor

class ProfileEvaluator:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.limiter = AsyncTokenBucket(capacity=5.0, fill_rate=5.0)
        self.client = httpx.AsyncClient(timeout=120.0)

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.client.aclose()

    async def _is_ollama_running(self, endpoint):
        try:
            res = await self.client.get(f"{endpoint.rstrip('/')}/api/tags")
            return res.status_code == 200
        except Exception:
            return False

    async def _is_kobold_running(self, endpoint):
        try:
            res = await self.client.get(f"{endpoint.rstrip('/')}/api/v1/model")
            return res.status_code == 200
        except Exception:
            return False

    async def _ensure_ollama_started(self, endpoint):
        if await self._is_ollama_running(endpoint):
            return True
        import time
        ollama_bin = os.path.expanduser(r"~\AppData\Local\Programs\Ollama\ollama.exe")
        if not os.path.isfile(ollama_bin):
            ollama_bin = "ollama"
        print(f"[+] ProfileEvaluator: Auto-launching local Ollama server ({ollama_bin})...")
        try:
            import subprocess
            subprocess.Popen([ollama_bin, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

            for _ in range(20):
                await asyncio.sleep(0.5)
                if await self._is_ollama_running(endpoint):
                    print("[+] ProfileEvaluator: Ollama server is online and ready!")
                    return True
        except Exception as e:
            print(f"[-] ProfileEvaluator: Failed to auto-launch Ollama: {e}")
        return False

    async def evaluate_session(self, db, session_id):
        """Analyzes a single chat session and extracts profile metrics and facts."""
        project_tag = None
        try:
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT project_tag FROM sessions WHERE session_id = ?", (session_id,))
                row = c.fetchone()
                if row:
                    project_tag = row["project_tag"]
                
                c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
                msgs = [dict(r) for r in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] ProfileEvaluator: Error reading session metadata or messages: {e}", file=sys.stderr)
            return False

        if not msgs:
            return False

        formatted_dialogue = [f"{msg['role']}: {msg['content']}" for msg in msgs]
        dialogue_text = "\n".join(formatted_dialogue)

        return await self.evaluate_dialogue(dialogue_text, db=db, session_id=session_id, project_tag=project_tag)

    async def evaluate_dialogue(self, dialogue_text, db=None, session_id=None, project_tag=None):
        """Core evaluation logic that processes raw dialogue text asynchronously."""
        if db:
            llm_provider = db.get_preference("llm_provider", "local_ollama")
            llm_model = db.get_preference("llm_model", "qwen2.5:7b-instruct")
            ollama_endpoint = db.get_preference("ollama_endpoint", "http://localhost:11434")
            kobold_endpoint = db.get_preference("kobold_endpoint", "http://localhost:5001")
            gemini_api_key = self.api_key or db.get_preference("gemini_api_key")
        else:
            llm_provider = "local_ollama"
            llm_model = "qwen2.5:7b-instruct"
            ollama_endpoint = "http://localhost:11434"
            kobold_endpoint = "http://localhost:5001"
            gemini_api_key = self.api_key

        extractor = FactExtractor()
        candidates = extractor.get_candidates(dialogue_text)
        
        if not candidates:
            s_id = session_id[:8] if session_id else "unknown"
            print(f"[+] ProfileEvaluator: Session {s_id} has no high-signal content. Fast-profiling.")
            return True

        if len(dialogue_text) > 40000:
            dialogue_text = dialogue_text[-40000:]
        
        if len(dialogue_text) > 10000:
            excerpt_strings = [c[1] if isinstance(c, (tuple, list)) else str(c) for c in candidates]
            dialogue_text = "High-signal excerpts from session:\n" + "\n".join(excerpt_strings)

        prompt_instructions = (
            "You are a developer behavioral evaluator. Analyze this dialogue between a developer (Pilot) and their AI mentor (Vespera).\n"
            "Identify and extract the following: \n"
            "1. Milestones, 2. Strengths, 3. Weaknesses, 4. Habits, 5. Dynamics, 6. Vision, 7. Inquiry, 8. Fact.\n"
            "Your output MUST be a JSON object containing a list under the key 'metrics'.\n"
            "Each entry: {'category': ..., 'name': ..., 'description': ..., 'confidence': ...}\n"
            "Format your output as a raw JSON object."
        )

        await self.limiter.consume(1)
        metrics = []

        is_kobold_active = (llm_provider == "local_kobold" or 
                            (llm_provider == "local_ollama" and 
                             not await self._is_ollama_running(ollama_endpoint) and 
                             await self._is_kobold_running(kobold_endpoint)))

        if is_kobold_active:
            url = f"{kobold_endpoint.rstrip('/')}/v1/chat/completions"
            payload = {
                "model": "local",
                "messages": [
                    {"role": "system", "content": prompt_instructions},
                    {"role": "user", "content": f"Analyze this dialogue:\n\n{dialogue_text}"}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2
            }
            try:
                response = await self.client.post(url, json=payload)
                response.raise_for_status()
                raw_output = response.json()["choices"][0]["message"]["content"].strip()
                result = json.loads(raw_output)
                metrics = result.get("metrics", []) if isinstance(result, dict) else []
            except Exception as e:
                print(f"[-] ProfileEvaluator: Local KoboldCpp generation failed: {e}", file=sys.stderr)
                return False

        elif llm_provider == "local_ollama":
            if not await self._ensure_ollama_started(ollama_endpoint):
                return False
            
            url = f"{ollama_endpoint.rstrip('/')}/api/chat"
            payload = {
                "model": llm_model,
                "messages": [
                    {"role": "system", "content": prompt_instructions},
                    {"role": "user", "content": f"Analyze this dialogue:\n\n{dialogue_text}"}
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2}
            }
            try:
                response = await self.client.post(url, json=payload)
                response.raise_for_status()
                raw_output = response.json()["message"]["content"].strip()
                result = json.loads(raw_output)
                metrics = result.get("metrics", []) if isinstance(result, dict) else []
            except Exception as e:
                print(f"[-] ProfileEvaluator: Local Ollama generation failed: {e}", file=sys.stderr)
                return False

        elif llm_provider == "cloud_gemini":
            if not gemini_api_key:
                print("[-] ProfileEvaluator: Cloud Gemini chosen but no API key set.", file=sys.stderr)
                return False

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={gemini_api_key}"
            payload = {
                "contents": [{
                    "parts": [{"text": f"{prompt_instructions}\n\nDialogue:\n{dialogue_text}"}]
                }],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }
            
            self.limiter.consume(1)
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=90) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    raw_text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
                    result = json.loads(raw_text)
                    if isinstance(result, str):
                        try:
                            result = json.loads(result)
                        except Exception:
                            pass
                    metrics = result.get("metrics", []) if isinstance(result, dict) else []
            except Exception as e:
                print(f"[-] ProfileEvaluator: Cloud Gemini evaluation failed: {e}", file=sys.stderr)
                return False
        else:
            print(f"[-] ProfileEvaluator: Unknown LLM provider: {llm_provider}", file=sys.stderr)
            return False

        if not metrics or not isinstance(metrics, list):
            return True

        # 3. Write metrics to database if db is provided
        if db:
            for m in metrics:
                if not isinstance(m, dict):
                    continue
                category = m.get("category")
                name = m.get("name")
                description = m.get("description")
                confidence = m.get("confidence", 0.5)
                
                if category and name and description:
                    if category == 'fact':
                        # Route to facts table
                        db.upsert_fact(fact=description, category="technical", confidence=confidence, project_tag=project_tag)
                    else:
                        # Route to developer profile table
                        db.upsert_profile_metric(category, name, description, confidence, project_tag=project_tag)
        
        s_id = session_id[:8] if session_id else "unknown"
        print(f"[+] ProfileEvaluator: Successfully evaluated session {s_id} and extracted {len(metrics)} items.")
        return metrics if metrics else True
