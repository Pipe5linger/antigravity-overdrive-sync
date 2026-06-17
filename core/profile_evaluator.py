import os
import sys
import json
import urllib.request
import urllib.error
import sqlite3
import requests
from core.utils import TokenBucket

class ProfileEvaluator:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.limiter = TokenBucket(capacity=5.0, fill_rate=0.25)

    def evaluate_session(self, db, session_id):
        """Analyzes a single chat session and extracts profile metrics."""
        # 1. Fetch preferences from the db
        llm_provider = db.get_preference("llm_provider", "local_ollama")
        llm_model = db.get_preference("llm_model", "qwen2.5-coder:14b")
        ollama_endpoint = db.get_preference("ollama_endpoint", "http://localhost:11434")
        gemini_api_key = self.api_key or db.get_preference("gemini_api_key")

        # 2. Fetch messages for session
        try:
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT role, content FROM messages WHERE session_id =  ? ORDER BY created_at ASC", (session_id,))
                msgs = [dict(r) for r in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] ProfileEvaluator: Error reading messages: {e}", file=sys.stderr)
            return False

        if not msgs:
            return False

        formatted_dialogue = []
        for msg in msgs:
            formatted_dialogue.append(f"{msg['role']}: {msg['content']}")
        dialogue_text = "\n".join(formatted_dialogue)

        if len(dialogue_text) > 40000:
            dialogue_text = dialogue_text[-40000:]

        prompt_instructions = (
            "You are a developer behavioral evaluator. Analyze this dialogue between a developer (Pilot) and their AI mentor (Vespera).\n"
            "Identify and extract the following: \n"
            "1. Milestones: Major tasks completed, tools successfully set up, or skills mastered.\n"
            "2. Strengths: Concepts, technologies, or commands the developer demonstrates good understanding of.\n"
            "3. Weaknesses: Knowledge gaps, errors made, or logical misunderstandings.\n"
            "4. Habits: Repeated developer practices, either good or bad.\n"
            "5. Dynamics: Shifts in the relationship, communication style, or emotional states (e.g., 'Operator displaying high frustration with Windows paths').\n"
            "6. Vision: The developer's personal thoughts, hypotheses, architectural visions, or design philosophies.\n"
            "7. Inquiry: Significant, unresolved technical questions or doubts raised by the developer.\n\n"
            "Your output MUST be a JSON object containing a list under the key 'metrics'. Each entry must have:\n"
            "- 'category': Must be one of 'milestone', 'strength', 'weakness', 'habit', 'dynamic', 'vision', 'inquiry'\n"
            "- 'name': A unique slug-like identifier (lowercase, words separated by hyphens, maximum 30 chars, e.g. 'vscode-search-hotkeys')\n"
            "- 'description': A short, clear description explaining what the developer did, understood, thought, or asked.\n"
            "- 'confidence': A float score between 0.1 and 1.0 representing your certainty of this assessment.\n"
            "Be highly critical, technical, and objective. Only capture metrics that are explicitly evidenced in the text.\n"
            "Format your output as a raw JSON object matching the requested schema."
        )

        metrics = []

        if llm_provider == "local_ollama":
            url = f"{ollama_endpoint.rstrip('/')}/api/generate"
            payload = {
                "model": llm_model,
                "prompt": f"Analyze this dialogue:\n\n_{dialogue_text}",
                "system": prompt_instructions,
                "stream": False,
                "format": "json"
            }
            try:
                response = requests.post(url, json=payload, timeout=120)
                response.raise_for_status()
                raw_output = response.json().get("response", "{}").strip()
                result = json.loads(raw_output)
                metrics = result.get("metrics", [])
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
                    metrics = result.get("metrics", [])
            except Exception as e:
                print(f"[-] ProfileEvaluator: Cloud Gemini evaluation failed: {e}", file=sys.stderr)
                return False
        else:
            print(f"[-] ProfileEvaluator: Unknown LLM provider: {llm_provider}", file=sys.stderr)
            return False

        if not metrics:
            return True

        # 3. Write metrics to database
        for m in metrics:
            category = m.get("category")
            name = m.get("name")
            description = m.get("description")
            confidence = m.get("confidence", 0.5)
            
            if category and name and description:
                db.upsert_profile_metric(category, name, description, confidence)
        
        print(f"[+] ProfileEvaluator: Successfully evaluated session {session_id[:8]} and extracted {len(metrics)} profile metrics.")
        return True
