import os
import time
import yaml
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from injectors.base import BaseInjector

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

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
        wait_time = (tokens - self.tokens) / self.fill_rate
        time.sleep(wait_time)
        self.tokens = 0
        self.last_fill = time.time()
        return True

class GeminiMdInjector(BaseInjector):
    TECH_KEYWORDS = ["ETL", "STREAM", "ATOMIC", "MEMORY", "PORTABLE", "STABLE DIFFUSION", "COMFYUI", "FLUX", "LORA", "GIT", "SCHEDULER", "O(1)"]
    
    def __init__(self, target_file=None, provider="ollama", model="llama3", llm_model=None, vector_model=None):
        super().__init__(target_file)
        self.provider = provider
        self.model = llm_model if llm_model else model
        self.vector_model = vector_model
        self.limiter = TokenBucket(capacity=5.0, fill_rate=0.25)

    def generate_summary(self, logs):
        if self.provider == "ollama" and HAS_OLLAMA:
            return self._generate_ollama(logs)
        return self._generate_gemini(logs)

    def _generate_ollama(self, logs):
        formatted = "\n".join([f"{m.get('sender')}: {m.get('text')}" for m in logs])
        prompt = f"Summarize technical achievements: {formatted}"
        try:
            res = ollama.generate(model=self.model, prompt=prompt)
            return res['response'].strip().replace("\n", " ")
        except Exception as e:
            print(f"[-] Ollama failed: {e}")
            return None

    def _generate_gemini(self, logs):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: return None
        
        formatted = "\n".join([f"{m.get('sender')}: {m.get('text')}" for m in logs])
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": f"Summarize: {formatted}"}]}]}
        
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=90) as res:
                data = json.loads(res.read().decode())
                return data['candidates'][0]['content']['parts'][0]['text'].strip().replace("\n", " ")
        except Exception as e:
            print(f"[-] Gemini failed: {e}")
            return None

    def compile_summaries_to_dict(self, db):
        import sqlite3
        compiled = []
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT session_id, updated_at, summary FROM sessions ORDER BY updated_at DESC")
            for row in c.fetchall():
                c.execute("SELECT role, content FROM messages WHERE session_id = ?", (row["session_id"],))
                msgs = [dict(r) for r in c.fetchall()]
                summary = row["summary"]
                
                if not summary:
                    print(f"[*] Generating {self.provider} summary for {row['session_id'][:8]}...")
                    self.limiter.consume(1)
                    summary = self.generate_summary([{"sender": m["role"], "text": m["content"]} for m in msgs])
                    if summary:
                        c.execute("UPDATE sessions SET summary = ? WHERE session_id = ?", (summary, row["session_id"]))
                
                compiled.append({"id": row["session_id"][:8], "summary": summary or "No summary available."})
            conn.commit()
        return compiled

    def inject(self, db, dry_run=False):
        # (Retain your existing atomic write/pointer logic here)
        return True