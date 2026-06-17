import os
import tempfile
import time
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


def atomic_write(file_path, content, mode="w", encoding="utf-8"):
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

        os.replace(tmp_file_name, target_path)
    except Exception as e:
        if tmp_file_name and Path(tmp_file_name).exists():
            os.unlink(tmp_file_name)
        raise RuntimeError(f"Atomic write failed: {e}") from e