import os
import csv
import datetime
import threading

# Project root is one level up from this file
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_PATH = os.path.join(BASE_DIR, "token_usage_log.csv")

_lock = threading.Lock()

def log(tool_name: str, prompt: str = "", completion: str = "") -> None:
    """Append a token‑usage entry to CSV.
    Token count is approximated by ``len(text)//4`` – the same heuristic used
    elsewhere in the codebase.
    """
    prompt_tokens = len(prompt) // 4
    completion_tokens = len(completion) // 4
    total = prompt_tokens + completion_tokens
    row = [datetime.datetime.utcnow().isoformat(), tool_name, prompt_tokens, completion_tokens, total]
    with _lock:
        write_header = not os.path.exists(LOG_PATH)
        with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["timestamp", "tool_name", "prompt_tokens", "completion_tokens", "total_tokens"]) 
            writer.writerow(row)

