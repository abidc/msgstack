"""Simple in-process sliding-window rate limiter.

No external dependencies — uses a deque of timestamps per key.
Thread-safe for single-process deployments. For multi-process (gunicorn),
replace with Redis-backed slowapi or similar.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

from src.config import settings

_windows: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def _check(key: str, limit: int, window_secs: int = 60) -> None:
    now = time.time()
    cutoff = now - window_secs
    with _lock:
        dq = _windows[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} requests per {window_secs}s",
                headers={"Retry-After": str(window_secs)},
            )
        dq.append(now)


def rate_limit(endpoint_key: str, request: Request, limit: int | None = None) -> None:
    """Call this at the top of rate-limited endpoints.

    Uses client IP as the rate-limit bucket key.
    """
    ip = request.client.host if request.client else "unknown"
    bucket = f"{endpoint_key}:{ip}"
    effective_limit = limit or settings.rate_limit_default
    _check(bucket, effective_limit)


def extract_limiter(request: Request) -> None:
    rate_limit("extract", request, settings.rate_limit_extract)


def generate_limiter(request: Request) -> None:
    rate_limit("generate", request, settings.rate_limit_generate)
