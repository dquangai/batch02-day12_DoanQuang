"""Redis-backed sliding-window rate limiter."""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

import redis
from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings

_redis: redis.Redis | None = None
_redis_error: str | None = None
_last_redis_attempt = 0.0
_redis_retry_after_seconds = 5.0
_local_windows: dict[str, deque[float]] = defaultdict(deque)


def redis_client() -> redis.Redis | None:
    global _redis, _redis_error, _last_redis_attempt
    if _redis is not None:
        return _redis
    now = time.time()
    if _redis_error and now - _last_redis_attempt < _redis_retry_after_seconds:
        if settings.require_redis:
            raise RedisError(_redis_error)
        return None
    _last_redis_attempt = now
    try:
        client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
        client.ping()
        _redis = client
        _redis_error = None
        return _redis
    except RedisError as exc:
        _redis_error = str(exc)
        if settings.require_redis:
            raise
        return None


def redis_status() -> dict:
    client = redis_client()
    if client is None:
        return {"connected": False, "error": _redis_error}
    try:
        client.ping()
        return {"connected": True}
    except RedisError as exc:
        return {"connected": False, "error": str(exc)}


def check_rate_limit(user_id: str) -> dict:
    """Allow at most RATE_LIMIT_PER_MINUTE requests per user per minute."""
    limit = settings.rate_limit_per_minute
    window_seconds = settings.rate_limit_window_seconds
    now = time.time()

    client = redis_client()
    if client is not None:
        key = f"rate:{user_id}"
        cutoff = now - window_seconds
        try:
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            _, count = pipe.execute()

            if count >= limit:
                oldest = client.zrange(key, 0, 0, withscores=True)
                retry_after = window_seconds
                if oldest:
                    retry_after = max(1, int(oldest[0][1] + window_seconds - now) + 1)
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": limit,
                        "window_seconds": window_seconds,
                        "retry_after_seconds": retry_after,
                    },
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(retry_after),
                    },
                )

            member = f"{now:.6f}:{uuid.uuid4().hex}"
            pipe = client.pipeline()
            pipe.zadd(key, {member: now})
            pipe.expire(key, window_seconds * 2)
            pipe.execute()
            remaining = limit - count - 1
            return {"limit": limit, "remaining": remaining, "storage": "redis"}
        except HTTPException:
            raise
        except RedisError:
            if settings.require_redis:
                raise HTTPException(status_code=503, detail="Rate limiter storage unavailable")

    bucket = _local_windows[user_id]
    while bucket and bucket[0] < now - window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": limit,
                "window_seconds": window_seconds,
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
    bucket.append(now)
    return {"limit": limit, "remaining": limit - len(bucket), "storage": "local-dev"}
