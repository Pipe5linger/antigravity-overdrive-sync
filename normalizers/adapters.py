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
            return normalized, None, []
            
        try:
            data = json.loads(file_content)
            # Support Google AI Studio exported prompts (chunkedPrompt format)
            if isinstance(data, dict) and "chunkedPrompt" in data:
                chunks = data.get("chunkedPrompt", {}).get("chunks", [])
                for chunk in chunks:
                    if not isinstance(chunk, dict):
                        continue
                    if chunk.get("isThought", False):
                        continue
                    role = chunk.get("role", "")
                    text = (chunk.get("text") or "").strip()
                    if not text and "driveDocument" in chunk:
                        doc = chunk.get("driveDocument", {})
                        title = doc.get("title", "Attached File")
                        text = f"[Attached Drive Document: {title}]"
                    
                    if len(text) > 5:
                        sender = "Pilot" if role == "user" else "Vespera"
                        normalized.append({
                            "sender": sender,
                            "text": text,
                            "timestamp": chunk.get("createTime") or datetime.now().isoformat()
                        })
                return normalized, None, []

            # Handle object with 'messages' list (Gemini Exporter) or raw array
            entries = data.get("messages", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                role = entry.get("role", "")
                contents = entry.get("contents", [])
                text = ""
                
                # Check for Gemini Exporter structured contents array
                if contents and isinstance(contents, list):
                    parts = []
                    for c in contents:
                        if isinstance(c, dict):
                            if c.get("type") == "text":
                                parts.append(c.get("content", ""))
                            elif c.get("type") == "attachment":
                                att = c.get("attachment", {})
                                name = att.get("name", "file")
                                parts.append(f"[Attached: {name}]")
                    text = "\n".join(parts).strip()
                
                if not text:
                    text = (entry.get("say") or entry.get("content") or entry.get("text") or "").strip()
                
                if len(text) > 0:
                    sender = "Pilot" if role in ["user", "Prompt", "user_feedback"] else "Vespera"
                    ts_raw = entry.get("time") or entry.get("created_at") or entry.get("ts")
                    timestamp = None
                    if ts_raw:
                        for fmt in ["%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                            try:
                                timestamp = datetime.strptime(ts_raw, fmt).isoformat()
                                break
                            except Exception:
                                pass
                    if not timestamp:
                        timestamp = ts_raw if ts_raw else datetime.now().isoformat()
                    
                    normalized.append({
                        "sender": sender,
                        "text": text,
                        "timestamp": timestamp
                    })
        except json.JSONDecodeError:
            print("[-] GeminiNormalizer: Failed to parse JSON.")
        return normalized, None, []

class AntigravityNormalizer:
    def parse(self, file_content):
        """Adapter for your existing .jsonl system generated logs."""
        normalized = []
        failed_tools = []
        project_tag = None
        last_tool_call = None

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
                
                # Keep track of last tool call to correlate with output
                if "tool_calls" in event:
                    tcs = event.get("tool_calls", [])
                    if tcs:
                        last_tool_call = tcs[0]

                event_type = event.get("type")
                text = event.get("content", "").strip()

                if event_type in ["USER_INPUT", "PLANNER_RESPONSE", "MODEL_RESPONSE"]:
                    # NOISE FILTER: Skip empty or very short system stubs
                    if text and len(text) > 10:
                        normalized.append({
                            "sender": "Pilot" if event_type == "USER_INPUT" else "Vespera",
                            "text": text,
                            "timestamp": event.get("created_at")
                        })
                
                # Extract Tool failures
                if event_type == "GENERIC" and text and "exited with code" in text:
                    code_str = text.split("exited with code")[1].split(".")[0].strip()
                    try:
                        exit_code = int(code_str)
                    except ValueError:
                        exit_code = 0
                        
                    if exit_code != 0:
                        cmd = "Unknown Command"
                        if last_tool_call:
                            args = last_tool_call.get("args", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except:
                                    pass
                            cmd = args.get("CommandLine", cmd)
                        
                        failed_tools.append({
                            "command": cmd,
                            "stderr": text,
                            "exit_code": exit_code,
                            "timestamp": event.get("created_at")
                        })

            except json.JSONDecodeError:
                continue
        return normalized, project_tag, failed_tools

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
        return normalized, project_tag, []
