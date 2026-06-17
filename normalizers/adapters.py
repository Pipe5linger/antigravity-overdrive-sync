import json
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
        return normalized

class AntigravityNormalizer:
    def parse(self, file_content):
        """Adapter for your existing .jsonl system generated logs."""
        normalized = []
        for line in file_content.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
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
        return normalized