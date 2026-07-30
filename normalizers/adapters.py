import json
import os
from datetime import datetime

class GeminiNormalizer:
    def parse(self, file_content):
        """Adapter for manually exported Gemini chat JSON or Markdown files."""
        normalized = []
        
        # Check if the content is Markdown
        if file_content.strip().startswith("#") or "## Prompt:" in file_content:
            current_role = None
            current_lines = []
            
            for line in file_content.splitlines():
                if line.startswith("## Prompt:"):
                    # Save previous block
                    if current_role and current_lines:
                        text = "\n".join(current_lines).strip()
                        if len(text) > 10:
                            normalized.append({
                                "sender": current_role,
                                "text": text,
                                "timestamp": datetime.now().isoformat()
                            })
                    current_role = "Pilot"
                    current_lines = []
                elif line.startswith("## Response:"):
                    # Save previous block
                    if current_role and current_lines:
                        text = "\n".join(current_lines).strip()
                        if len(text) > 10:
                            normalized.append({
                                "sender": current_role,
                                "text": text,
                                "timestamp": datetime.now().isoformat()
                            })
                    current_role = "Vespera"
                    current_lines = []
                elif line.startswith("## ") and not line.startswith("## Prompt:") and not line.startswith("## Response:"):
                    # Any other heading resets current role
                    if current_role and current_lines:
                        text = "\n".join(current_lines).strip()
                        if len(text) > 10:
                            normalized.append({
                                "sender": current_role,
                                "text": text,
                                "timestamp": datetime.now().isoformat()
                            })
                    current_role = None
                    current_lines = []
                else:
                    if current_role:
                        current_lines.append(line)
            
            # Save final block
            if current_role and current_lines:
                text = "\n".join(current_lines).strip()
                if len(text) > 10:
                    normalized.append({
                        "sender": current_role,
                        "text": text,
                        "timestamp": datetime.now().isoformat()
                    })
            return normalized, None
            
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

class ClineNormalizer:
    def parse(self, file_content):
        """Adapter for Roo-Cline and Cline VS Code extension chat JSON transcripts."""
        normalized = []
        project_tag = None
        try:
            data = json.loads(file_content)
            # Support both array of UI messages and api_conversation_history format
            messages = data if isinstance(data, list) else data.get("messages", [])
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role") or msg.get("type") or msg.get("say")
                text = msg.get("content") or msg.get("text")
                if isinstance(text, list):
                    # Handle multimodal content blocks
                    text_parts = [b.get("text", "") for b in text if isinstance(b, dict) and b.get("type") == "text"]
                    text = "\n".join(text_parts)
                if not text or not isinstance(text, str):
                    continue
                text = text.strip()
                if len(text) > 10 and not text.startswith("[API Error"):
                    sender = "Pilot" if role in ["user", "user_feedback"] else "Vespera"
                    normalized.append({
                        "sender": sender,
                        "text": text,
                        "timestamp": datetime.fromtimestamp(msg.get("ts", 0)/1000).isoformat() if msg.get("ts") else datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"[-] ClineNormalizer: Error parsing Cline log: {e}")
        return normalized, project_tag