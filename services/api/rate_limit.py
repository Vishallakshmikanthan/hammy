"""
HAMMY — Rate Limiting Dependency (`services/api/rate_limit.py`).
Provides sliding-window in-memory rate limiting per client IP / authenticated user.
"""

from __future__ import annotations

import collections
import time
from typing import Dict, Deque, Optional
from fastapi import HTTPException, Request, status


class RateLimiter:
    """Sliding-window in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self.window_sec = 60.0
        self._history: Dict[str, Deque[float]] = collections.defaultdict(collections.deque)

    def check(self, request: Request, identifier: Optional[str] = None) -> None:
        key = identifier or request.client.host if request.client else "unknown_client"
        now = time.time()
        window_start = now - self.window_sec

        queue = self._history[key]
        while queue and queue[0] < window_start:
            queue.popleft()

        if len(queue) >= self.requests_per_minute:
            retry_after = int(self.window_sec - (now - queue[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait before submitting more requests.",
                headers={"Retry-After": str(max(1, retry_after))},
            )

        queue.append(now)

    def reset(self) -> None:
        self._history.clear()


# Global default rate limiter
global_rate_limiter = RateLimiter(requests_per_minute=120)


def rate_limit_dependency(request: Request) -> None:
    """FastAPI route dependency to apply rate limiting."""
    global_rate_limiter.check(request)

