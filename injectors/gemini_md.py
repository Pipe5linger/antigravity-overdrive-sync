# D:\AI\Projects\antigravity-overdrive-sync\injectors\gemini_md.py
import os
import time
import yaml
import json
import urllib.request
import urllib.error
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Union, Dict, Any
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
    TECH_KEYWORDS: List[str] = ["ETL", "STREAM", "ATOMIC", "MEMORY", "PORTABLE", "STABLE DIFFUSION", "COMFYUI", "FLUX", "LORA", "GIT", "SCHEDULER", "O(1)"]
    
    def __init__(
        self, 
        target_file: Optional[Union[str, Path]] = None, 
        provider: str = "ollama", 
        model: str = "llama3", 
        llm_model: Optional[str] = None, 
        vector_model: Optional[str] = None
    ) -> None:
        super().__init__(target_file)
        self.provider: str = provider
        self.model: str = llm_model if llm_model else model
        self.vector_model: Optional[str] = vector_model
        self.limiter: TokenBucket = TokenBucket(capacity=5.0, fill_rate=0.25)

    def generate_summary(self, logs: List[Dict[str, Any]]) -> Optional[str]:
        effective_provider: str = self.provider
        
        if self.provider == "ollama":
            is_ollama_alive: bool = False
            if HAS_OLLAMA:
                try:
                    res = requests.get("http://localhost:11434/api/tags", timeout=2)
                    is_ollama_alive = (res.status_code == 200)
                except Exception:
                    pass
            
            if not is_ollama_alive:
                try:
                    res = requests.get("http://localhost:5001/api/v1/model", timeout=2)
                    if res.status_code == 200:
                        effective_provider = "kobold"
                        print("[*] GeminiMdInjector: Ollama offline, auto-routing summary generation to active KoboldCpp on port 5001.")
                except Exception:
                    pass

        if effective_provider == "kobold":
            return self._generate_kobold(logs)
        if effective_provider == "ollama" and HAS_OLLAMA:
            return self._generate_ollama(logs)
        return self._generate_gemini(logs)

    async def generate_summary_async(self, logs: List[Dict[str, Any]]) -> Optional[str]:
        """Asynchronous non-blocking wrapper for summary generation."""
        import asyncio
        return await asyncio.to_thread(self.generate_summary, logs)

    def _generate_kobold(self, logs):
        formatted = "\n".join([f"{m.get('sender')}: {m.get('text')}" for m in logs])
        prompt = (
            "Summarize the technical achievements, tools used, and issues resolved in this developer chat session. "
            "Be extremely clear, objective, and keep it under 3 sentences.\n\n"
            f"Chat Log:\n{formatted}"
        )
        
        url = "http://localhost:5001/v1/chat/completions"
        payload = {
            "model": "local",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5
        }
        try:
            res = requests.post(url, json=payload, timeout=90)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"].strip().replace("\n", " ")
        except Exception as e:
            try:
                native_url = "http://localhost:5001/api/v1/generate"
                native_payload = {
                    "prompt": prompt,
                    "max_length": 150,
                    "temperature": 0.5
                }
                res = requests.post(native_url, json=native_payload, timeout=90)
                res.raise_for_status()
                return res.json()["results"][0]["text"].strip().replace("\n", " ")
            except Exception as e2:
                print(f"[-] GeminiMdInjector: KoboldCpp generation failed: {e} | Native: {e2}")
                return None

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
            # Fetch recent 15 sessions max to prevent infinite historical profiling loops
            c.execute("SELECT session_id, updated_at, summary FROM sessions ORDER BY updated_at DESC LIMIT 15")
            rows = c.fetchall()
            
            for row in rows:
                c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 20", (row["session_id"],))
                msgs = [dict(r) for r in c.fetchall()]
                summary = row["summary"]
                
                if not summary and msgs:
                    print(f"[*] Generating fast summary for active session {row['session_id'][:8]}...")
                    summary = self.generate_summary([{"sender": m["role"], "text": m["content"]} for m in reversed(msgs)])
                    if summary:
                        c.execute("UPDATE sessions SET summary = ? WHERE session_id = ?", (summary, row["session_id"]))
                    else:
                        # Fallback to default summary to avoid repeating re-summarization loop
                        summary = "Session state active."
                        c.execute("UPDATE sessions SET summary = ? WHERE session_id = ?", (summary, row["session_id"]))
                
                compiled.append({"id": row["session_id"][:8], "summary": summary or "Session state active."})
            
            # Batch update all older un-summarized historical sessions with default tag so they are never queried again
            c.execute("UPDATE sessions SET summary = 'Archived session log.' WHERE summary IS NULL OR summary = ''")
            conn.commit()
        return compiled

    def inject(self, db, dry_run=False):
        try:
            from core.assembler import DynamicPromptAssembler
            target_path = self.target_file or r"D:\AI\GEMINI.md"
            assembler = DynamicPromptAssembler(db.db_path)
            compiled_prompt = assembler.assemble_prompt()
            
            if not dry_run:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(compiled_prompt)
                print(f"[+] Successfully injected updated system protocol into: {target_path}")
            return True
        except Exception as e:
            print(f"[-] GeminiMdInjector injection failed: {e}")
            return False