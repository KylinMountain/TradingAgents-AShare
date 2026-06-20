"""令牌桶限速器 — 上限160次/分（200*0.8，预留20%防封禁）"""

import time
import threading


class RateLimiter:
    def __init__(self, max_calls_per_minute: int = 160):
        self.max_tokens = max_calls_per_minute
        self.tokens = float(max_calls_per_minute)
        self.refill_rate = max_calls_per_minute / 60.0  # tokens/sec
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens < 1.0:
                sleep_time = (1.0 - self.tokens) / self.refill_rate
                time.sleep(sleep_time)
                self.tokens = 0.0
                self.last_refill = time.monotonic()
            else:
                self.tokens -= 1.0

    @property
    def available(self) -> float:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            return min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
