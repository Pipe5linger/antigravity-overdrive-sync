import os
import tempfile
import time
import asyncio
import requests
from pathlib import Path


class TokenBucket:
    """Thread-safe token bucket rate limiter. Single canonical definition for the pipeline."""

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


class AsyncTokenBucket:
    """Asynchronous token bucket rate limiter for asyncio-based worker pools."""

    def __init__(self, capacity, fill_rate):
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = capacity
        self.last_fill = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens=1):
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_fill
            self.last_fill = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            required_tokens = tokens - self.tokens
            wait_time = required_tokens / self.fill_rate
            await asyncio.sleep(wait_time)
            self.tokens = 0
            self.last_fill = time.time()
            return True


def atomic_write(file_path, content, mode="w", encoding="utf-8", retries=3):
    tmp_file_name = None
    try:
        target_path = Path(file_path)
        parent_dir = target_path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode, delete=False, dir=parent_dir, encoding=encoding
        ) as tmp_file:
            tmp_file_name = tmp_file.name
            tmp_file.write(content)

        # Retry loop for Windows file locking contention
        last_err = None
        for attempt in range(retries):
            try:
                os.replace(tmp_file_name, target_path)
                return True
            except (PermissionError, OSError) as e:
                last_err = e
                time.sleep(0.05 * (2 ** attempt))

        if last_err:
            raise last_err
    except Exception as e:
        if tmp_file_name and Path(tmp_file_name).exists():
            try:
                os.unlink(tmp_file_name)
            except Exception:
                pass
        raise RuntimeError(f"Atomic write failed: {e}") from e


def shutdown_ollama(endpoint="http://localhost:11434", log_callback=None):
    """Unloads all loaded VRAM models and stops the Ollama server process."""
    def log(msg):
        print(msg)
        if log_callback:
            try:
                log_callback(msg)
            except Exception:
                pass

    log("[*] Shutting down Ollama and purging VRAM...")
    base = endpoint.rstrip("/")

    # 1. Purge models from VRAM via keep_alive=0
    try:
        res = requests.get(f"{base}/api/ps", timeout=3)
        if res.status_code == 200:
            running_models = res.json().get("models", [])
            for m in running_models:
                m_name = m.get("name")
                if m_name:
                    try:
                        requests.post(f"{base}/api/generate", json={"model": m_name, "keep_alive": 0}, timeout=5)
                        log(f"[+] Purged {m_name} from VRAM.")
                    except Exception:
                        pass
    except Exception:
        pass

    # 2. Terminate the Ollama process on Windows / OS
    try:
        import subprocess
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/IM", "ollama.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "ollama_llama_server.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-f", "ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("[+] Ollama server process terminated.")
    except Exception as e:
        log(f"[-] Failed to terminate Ollama process: {e}")


SECRET_PATTERNS = [
    # Google Gemini API keys
    r'AIza[0-9A-Za-z-_]{35}',
    # OpenAI / Anthropic keys
    r'sk-[A-Za-z0-9-_]{20,}',
    # Stripe live secret keys
    r'sk_live_[0-9a-zA-Z]{24,}',
    # AWS access key IDs
    r'AKIA[0-9A-Z]{16}',
    # Slack bot/user tokens
    r'xox[baprs]-[0-9a-zA-Z-]{10,}',
    # Hugging Face tokens
    r'hf_[a-zA-Z0-9]{34,}',
    # GitHub personal access tokens
    r'gh[pousr]_[A-Za-z0-9_]{36,}',
    # JSON Web Tokens (JWT)
    r'eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}',
    # Private Key blocks
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----',
    # URLs with embedded username:password
    r'https?://[^:\s]+:[^@\s]+@[^\s]+',
    # Generic config assignment lines (e.g. API_KEY='...', password="...")
    r'(?i)(?:password|api_key|secret|token)\s*=\s*[\'"][^\'"]{8,}[\'"]',
    # Unquoted assignment lines (e.g. API_KEY=xyz12345678)
    r'(?i)(?:password|api_key|secret|token)\s*=\s*[^\s\'"]{8,}',
    # JSON property secret assignments (e.g. "password": "...", "api_key": "...")
    r'(?i)"(?:password|api_key|secret|token)"\s*:\s*"[^"]{8,}"',
    # Generic bearer / auth header tokens
    r'(?i)(?:bearer\s+|token\s+|api_key\s*=\s*)[A-Za-z0-9_\-\.]{24,}'
]

def scrub_secrets(text: str) -> str:
    """Scrubs sensitive API keys, auth tokens, and credentials from text before logging or storing."""
    if not text or not isinstance(text, str):
        return text
    import re
    scrubbed = text
    for pat in SECRET_PATTERNS:
        scrubbed = re.sub(pat, '[REDACTED_SECRET]', scrubbed)
    return scrubbed