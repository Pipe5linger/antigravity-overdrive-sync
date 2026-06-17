import json
import os
from datetime import datetime

class GeminiNormalizer:
    def parse(self, file_content):
        """Adapter for manually exported Gemini chat JSON files."""
        normalized = []
        try:
            data = json.loads(file_content)
            for entry in data:
                text = entry.get("content", "").strip()
                # NOISE FILTER: Skip empty or very short system stubs
                if len(text) > 10:
                    normalized.append({
                        "sender": "Pilot" if entry.get("role") == "user" else "Vespera",
                        "text": text,
                        "timestamp": entry.get("created_at", datetime.now().isoformat())
                    })
        except json.JSONDecodeError:
            print("[-] GeminiNormalizer: Failed to parse JSON.")
        return normalized, None

class AntigravityNormalizer:
    def parse(self, file_content):
        """Adapter for your existing .jsonl system generated logs."""
        normalized = []
        project_tag = None
        for line in file_content.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                
                # Check for Cwd in tool_calls to identify active project workspace tag
                if not project_tag and "tool_calls" in event:
                    for tc in event.get("tool_calls", []):
                        args = tc.get("args", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except:
                                pass
                        if isinstance(args, dict) and "Cwd" in args:
                            cwd_val = args["Cwd"]
                            if cwd_val and isinstance(cwd_val, str):
                                project_tag = os.path.basename(cwd_val.strip().strip('"\'').rstrip("\\/"))
                
                event_type = event.get("type")
                if event_type in ["USER_INPUT", "PLANNER_RESPONSE", "MODEL_RESPONSE"]:
                    text = event.get("content", "").strip()
                    # NOISE FILTER: Skip empty or very short system stubs
                    if text and len(text) > 10:
                        normalized.append({
                            "sender": "Pilot" if event_type == "USER_INPUT" else "Vespera",
                            "text": text,
                            "timestamp": event.get("created_at")
                        })
            except json.JSONDecodeError:
                continue
        return normalized, project_tag