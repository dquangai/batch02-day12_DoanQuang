"""Monthly budget guard for LLM usage."""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.rate_limiter import redis_client

_local_spend: dict[str, float] = defaultdict(float)


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    input_cost = input_tokens / 1000 * settings.input_price_per_1k_tokens
    output_cost = output_tokens / 1000 * settings.output_price_per_1k_tokens
    return round(input_cost + output_cost, 8)


def _month_key(user_id: str) -> str:
    month = time.strftime("%Y-%m", time.gmtime())
    return f"budget:{user_id}:{month}"


def current_spend(user_id: str) -> float:
    key = _month_key(user_id)
    client = redis_client()
    if client is not None:
        try:
            return float(client.get(key) or 0.0)
        except RedisError:
            if settings.require_redis:
                raise HTTPException(status_code=503, detail="Budget storage unavailable")
    return float(_local_spend[key])


def check_budget(user_id: str, estimated_cost: float = 0.0) -> bool:
    """Return True when the user remains inside the monthly budget."""
    used = current_spend(user_id)
    if used + estimated_cost > settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(used, 6),
                "estimated_cost_usd": round(estimated_cost, 6),
                "budget_usd": settings.monthly_budget_usd,
                "resets": "first day of next UTC month",
            },
        )
    return True


def record_usage(user_id: str, input_tokens: int, output_tokens: int) -> dict:
    cost = estimate_cost(input_tokens, output_tokens)
    key = _month_key(user_id)
    check_budget(user_id, cost)

    client = redis_client()
    if client is not None:
        try:
            total = float(client.incrbyfloat(key, cost))
            client.expire(key, 32 * 24 * 60 * 60)
            return {
                "cost_usd": cost,
                "monthly_spend_usd": round(total, 6),
                "budget_usd": settings.monthly_budget_usd,
                "storage": "redis",
            }
        except RedisError:
            if settings.require_redis:
                raise HTTPException(status_code=503, detail="Budget storage unavailable")

    _local_spend[key] += cost
    return {
        "cost_usd": cost,
        "monthly_spend_usd": round(_local_spend[key], 6),
        "budget_usd": settings.monthly_budget_usd,
        "storage": "local-dev",
    }
