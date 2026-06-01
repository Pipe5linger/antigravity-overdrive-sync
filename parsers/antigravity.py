import os
import json
from datetime import datetime
from parsers.base import BaseParser

class AntigravityParser(BaseParser):
    """Highly optimized stream-parser for Antigravity transcript.jsonl files."""
    
    def __init__(self, source_dir=None):
        if not source_dir:
            # Dynamically resolve home folder
            source_dir = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "brain")
        super().__init__(source_dir)
        
    def extract_transcript(self, filepath, session_id):
        """
        Parses transcript.jsonl line-by-line (O(1) memory complexity).
        Filters system noise and strips UI tags on the fly.
        """
        messages = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        event_type = event.get("type")
                        if event_type in ["USER_INPUT", "PLANNER_RESPONSE", "MODEL_RESPONSE"]:
                            sender = "Pilot" if event_type == "USER_INPUT" else "Vespera"
                            content = event.get("content", "").strip()
                            
                            # Strip XML tags from user inputs for clean reading
                            if event_type == "USER_INPUT":
                                content = content.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "").strip()
                                
                            if content:
                                messages.append({
                                    "sender": sender,
                                    "timestamp": event.get("created_at"),
                                    "text": content
                                })
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[-] Failed to read transcript {filepath}: {e}")
            
        return messages
        
    def fetch_new_logs(self):
        """Crawls the Antigravity Brain folder and streams payloads to the engine."""
        extracted_payloads = []
        
        if not os.path.exists(self.source_dir):
            print(f"[-] Brain directory not found at {self.source_dir}")
            return extracted_payloads
            
        for item in os.listdir(self.source_dir):
            session_dir = os.path.join(self.source_dir, item)
            if os.path.isdir(session_dir):
                transcript_path = os.path.join(session_dir, ".system_generated", "logs", "transcript.jsonl")
                if os.path.exists(transcript_path):
                    mtime = os.path.getmtime(transcript_path)
                    mtime_iso = datetime.fromtimestamp(mtime).isoformat()
                    
                    messages = self.extract_transcript(transcript_path, item)
                    if messages:
                        extracted_payloads.append({
                            "chat_id": item,
                            "last_mutated": mtime_iso,
                            "messages": messages
                        })
                        
        return extracted_payloads
