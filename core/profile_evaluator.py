import os
import sys
import json
import urllib.request
import urllib.error
import sqlite3
import datetime
import time
from pathlib import Path
from core.fact_extractor import QUOTA_LOCK_FILE, _check_quota_lock, _write_quota_lock
from core.utils import TokenBucket

class ProfileEvaluator:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.limiter = TokenBucket(capacity=5.0, fill_rate=0.25)
        self.quota_exhausted = _check_quota_lock()
        if self.quota_exhausted:
            import sys as _sys
            print("[-] ProfileEvaluator: Quota lock active (429 hit within last 24h). Skipping API calls.", file=_sys.stderr)
        if not self.api_key:
            try:
                env_path = Path(__file__).resolve().parents[1] / ".env"
                if env_path.exists():
                    with open(env_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip() and not line.startswith("#"):
                                parts = line.split("=", 1)
                                if len(parts) == 2 and parts[0].strip() == "GEMINI_API_KEY":
                                    self.api_key = parts[1].strip().strip('"').strip("'")
                                    break
            except:
                pass

    def evaluate_session(self, db, session_id):
        """Analyzes a single chat session and extracts profile metrics."""
        if self.quota_exhausted:
            return False
        if not self.api_key:
            print("[-] ProfileEvaluator: No API key found. Skipping evaluation.")
            return False

        # 1. Fetch messages for session
        try:
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
                msgs = [dict(r) for r in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] ProfileEvaluator: Error reading messages: {e}")
            return False

        if not msgs:
            return False

        formatted_dialogue = []
        for msg in msgs:
            formatted_dialogue.append(f"{msg['role']}: {msg['content']}")
        dialogue_text = "\n".join(formatted_dialogue)

        if len(dialogue_text) > 40000:
            dialogue_text = dialogue_text[-40000:]
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={self.api_key}"

        prompt = (
            "You are a developer behavioral evaluator. Analyze this dialogue between a developer (Pilot) and their AI mentor (Vespera).\n"
            "Identify and extract the following: \n"
            "1. Milestones: Major tasks completed, tools successfully set up, or skills mastered (e.g., 'Mastered VS Code search hotkeys').\n"
            "2. Strengths: Concepts, technologies, or commands the developer demonstrates good understanding of (e.g., 'Understands SQLite WAL mode').\n"
            "3. Weaknesses: Knowledge gaps, errors made, or logical misunderstandings (e.g., 'Using breakpoints to debug performance bottlenecks').\n"
            "4. Habits: Repeated developer practices, either good or bad (e.g., 'Staging commits without reviewing logs').\n\n"
            "Your output MUST be a JSON object containing a list under the key 'metrics'. Each entry must have:\n"
            "- 'category': Must be one of 'milestone', 'strength', 'weakness', 'habit'\n"
            "- 'name': A unique slug-like identifier (lowercase, words separated by hyphens, maximum 30 chars, e.g. 'vscode-search-hotkeys')\n"
            "- 'description': A short, clear description explaining what the developer did, understood, or failed to do.\n"
            "- 'confidence': A float score between 0.1 and 1.0 representing your certainty of this assessment.\n"
            "Be highly critical, technical, and objective. Only capture metrics that are explicitly evidenced in the text.\n"
            "Format your output as a raw JSON object matching the requested schema."
        )

        payload = {
            "contents": [{
                "parts": [{"text": f"{prompt}\n\nDialogue:\n{dialogue_text}"}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        max_retries = 4
        backoff = 6.0
        self.limiter.consume(1)
        for attempt in range(max_retries):
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
                    if not metrics:
                        return True
                    
                    # 2. Write metrics to database
                    for m in metrics:
                        category = m.get("category")
                        name = m.get("name")
                        description = m.get("description")
                        confidence = m.get("confidence", 0.5)
                        
                        if category and name and description:
                            db.upsert_profile_metric(category, name, description, confidence)
                    print(f"[+] ProfileEvaluator: Successfully evaluated session {session_id[:8]} and extracted {len(metrics)} profile metrics.")
                    return True
            except urllib.error.HTTPError as he:
                if he.code == 429:
                    self.quota_exhausted = True
                    _write_quota_lock()
                    print(f"[-] ProfileEvaluator: API quota exhausted (429) for session {session_id[:8]}. Halting.", file=sys.stderr)
                    return False
                print(f"[-] ProfileEvaluator: API HTTP Error {he.code} for session {session_id[:8]}: {he.reason}", file=sys.stderr)
                return False
            except Exception as e:
                print(f"[-] ProfileEvaluator: Evaluation failed for session {session_id[:8]}: {e}", file=sys.stderr)
                return False
        return False