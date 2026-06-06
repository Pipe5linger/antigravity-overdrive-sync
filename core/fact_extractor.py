import os
import sys
import json
import urllib.request
import urllib.error
import sqlite3
import time

class TokenBucket:
    def __init__(self, capacity, fill_rate):
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = capacity
        self.last_fill = time.time()

    def consume(self, tokens=1):
        now = time.time()
        elapsed = now - self.last_fill
        self.last_fill = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
            
        required_tokens = tokens - self.tokens
        wait_time = required_tokens / self.fill_rate
        time.sleep(wait_time)
        self.tokens = 0
        self.last_fill = time.time()
        return True

class FactExtractor:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.limiter = TokenBucket(capacity=5.0, fill_rate=0.25)
        self.quota_exhausted = False
        if not self.api_key:
            from pathlib import Path
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

    def extract_facts(self, db, session_id):
        """Analyzes a single chat session and extracts declarative facts to SQLite."""
        if not self.api_key:
            print("[-] FactExtractor: No API key found. Skipping.")
            return False

        try:
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
                msgs = [dict(r) for r in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] FactExtractor: Error reading messages: {e}")
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
            "You are a memory systems coordinator. Analyze the dialogue between a user (Pilot) and their AI mentor (Vespera).\n"
            "Identify and extract distinct, concrete, and factual information mentioned about the user. Only extract general, persistent facts.\n"
            "Examples of facts to extract:\n"
            "- Preferred programming languages, editors, libraries, and frameworks.\n"
            "- Operating systems, hardware specifications, and directories.\n"
            "- Background context (education, work experience, location, habits, preferences, personal history).\n"
            "- Direct statements of intent, plans, or setups.\n\n"
            "Your output MUST be a JSON object containing a list under the key 'facts'. Each entry must have:\n"
            "- 'fact': The declarative statement itself (e.g. 'User has NVMe drive mapped to D:\\' or 'User is learning Python'). Make it short and clear.\n"
            "- 'category': One of: 'technical', 'personal', 'workspace'\n"
            "- 'confidence': A float score between 0.5 and 1.0 representing your certainty of this fact.\n\n"
            "Only capture facts explicitly stated or strongly evidenced. Do not assume or extrapolate.\n"
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
                    
                    extracted_list = result.get("facts", [])
                    if not extracted_list:
                        return True
                    
                    for item in extracted_list:
                        fact_text = item.get("fact")
                        cat = item.get("category", "personal")
                        conf = item.get("confidence", 0.8)
                        if fact_text:
                            db.upsert_fact(fact_text, cat, conf)
                    print(f"[+] FactExtractor: Extracted {len(extracted_list)} facts from session {session_id[:8]}.")
                    return True
            except urllib.error.HTTPError as he:
                if he.code == 429:
                    self.quota_exhausted = True
                    print(f"[-] FactExtractor: API quota exhausted (429) for session {session_id[:8]}. Halting.", file=sys.stderr)
                    return False
                print(f"[-] FactExtractor: API HTTP Error {he.code} for session {session_id[:8]}: {he.reason}", file=sys.stderr)
                return False
            except Exception as e:
                print(f"[-] FactExtractor: Extraction failed for session {session_id[:8]}: {e}", file=sys.stderr)
                return False
        return False
