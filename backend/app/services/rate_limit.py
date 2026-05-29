"""Simple in-memory sliding-window rate limiter for FastAPI dependencies.

Usage:
    limiter = RateLimiter(max_calls=5, window_sec=60)

    @router.post("/login")
    def login(request: Request, _rl=Depends(limiter)):
        ...
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request

from ..envelope import EnvelopeError


class RateLimiter:
    def __init__(self, max_calls: int, window_sec: int) -> None:
        self._max = max_calls
        self._window = window_sec
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def reset(self) -> None:
        self._buckets.clear()

    def __call__(self, request: Request) -> None:
        ip = self._client_ip(request)
        now = time.monotonic()
        bucket = self._buckets[ip]
        cutoff = now - self._window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self._max:
            raise EnvelopeError(
                f"Too many requests. Limit: {self._max} per {self._window}s.",
                "RATE_LIMITED",
                429,
            )
        bucket.append(now)


login_limiter = RateLimiter(max_calls=5, window_sec=60)
infer_limiter = RateLimiter(max_calls=20, window_sec=60)
