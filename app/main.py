"""Production-ready AI agent for the Day 12 deployment lab."""
from __future__ import annotations

import json
import logging
import re
import signal
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import current_spend, estimate_cost, record_usage
from app.rate_limiter import check_rate_limit, redis_client, redis_status
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "event"):
            payload["event"] = record.event
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    handlers=[handler],
    force=True,
)
logger = logging.getLogger("production_agent")

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0
_local_history: dict[str, list[dict]] = defaultdict(list)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field("default", min_length=1, max_length=128)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    history_turns: int
    served_by: str
    usage: dict
    timestamp: str


def _history_key(user_id: str) -> str:
    return f"history:{user_id}"


def _load_history(user_id: str) -> list[dict]:
    client = redis_client()
    if client is not None:
        try:
            raw_messages = client.lrange(_history_key(user_id), 0, -1)
            return [json.loads(item) for item in raw_messages]
        except (RedisError, json.JSONDecodeError):
            if settings.require_redis:
                raise HTTPException(status_code=503, detail="Conversation storage unavailable")

    return list(_local_history[user_id])


def _append_history(user_id: str, role: str, content: str) -> list[dict]:
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    client = redis_client()
    if client is not None:
        try:
            key = _history_key(user_id)
            pipe = client.pipeline()
            pipe.rpush(key, json.dumps(message, ensure_ascii=False))
            pipe.ltrim(key, -settings.max_history_messages, -1)
            pipe.expire(key, settings.history_ttl_seconds)
            pipe.execute()
            return _load_history(user_id)
        except RedisError:
            if settings.require_redis:
                raise HTTPException(status_code=503, detail="Conversation storage unavailable")

    _local_history[user_id].append(message)
    _local_history[user_id] = _local_history[user_id][-settings.max_history_messages :]
    return list(_local_history[user_id])


def _contextual_answer(question: str, history: list[dict]) -> str:
    """Small context layer on top of the mock LLM for deterministic lab tests."""
    question_lower = question.lower()
    previous_user_messages = [
        item["content"] for item in history if item.get("role") == "user"
    ]

    if "what did i just say" in question_lower or "vừa nói" in question_lower:
        if previous_user_messages:
            return f'You just said: "{previous_user_messages[-1]}".'

    if "what is my name" in question_lower or "tên tôi" in question_lower:
        for message in reversed(previous_user_messages):
            match = re.search(r"\bmy name is\s+([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ .'-]{0,60})", message, re.I)
            if match:
                name = match.group(1).strip(" .,!?:;")
                return f"Your name is {name}."

    context_note = ""
    if previous_user_messages:
        context_note = f" Previous turn: {previous_user_messages[-1]}"
    return llm_ask(question) + context_note


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(
        json.dumps(
            {
                "event": "startup",
                "app": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
                "instance": settings.instance_id,
            }
        ),
        extra={"event": "startup"},
    )
    _is_ready = True
    yield
    _is_ready = False
    logger.info("graceful shutdown complete", extra={"event": "graceful_shutdown"})


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
    except Exception:
        _error_count += 1
        logger.exception("request failed", extra={"event": "request_error"})
        raise

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Served-By"] = settings.instance_id
    duration_ms = round((time.time() - start) * 1000, 1)
    logger.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }
        ),
        extra={"event": "request"},
    )
    return response


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance": settings.instance_id,
        "endpoints": {
            "ask": "POST /ask with X-API-Key",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics with X-API-Key",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
def ask_agent(body: AskRequest, _key_fingerprint: str = Depends(verify_api_key)):
    rate = check_rate_limit(body.user_id)
    input_tokens = max(1, len(body.question.split()) * 2)
    preflight_cost = estimate_cost(input_tokens, 256)
    if current_spend(body.user_id) + preflight_cost > settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget would be exceeded",
                "budget_usd": settings.monthly_budget_usd,
            },
        )

    history_before = _load_history(body.user_id)
    _append_history(body.user_id, "user", body.question)
    answer = _contextual_answer(body.question, history_before)
    history_after = _append_history(body.user_id, "assistant", answer)

    output_tokens = max(1, len(answer.split()) * 2)
    usage = record_usage(body.user_id, input_tokens, output_tokens)
    usage["rate_limit"] = rate

    user_turns = len([item for item in history_after if item.get("role") == "user"])
    logger.info(
        json.dumps(
            {
                "event": "agent_call",
                "user_id": body.user_id,
                "history_turns": user_turns,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        ),
        extra={"event": "agent_call"},
    )

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        history_turns=user_turns,
        served_by=settings.instance_id,
        usage=usage,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/history/{user_id}", tags=["Agent"])
def history(user_id: str, _key_fingerprint: str = Depends(verify_api_key)):
    messages = _load_history(user_id)
    return {"user_id": user_id, "messages": messages, "count": len(messages)}


@app.delete("/history/{user_id}", tags=["Agent"])
def delete_history(user_id: str, _key_fingerprint: str = Depends(verify_api_key)):
    client = redis_client()
    if client is not None:
        client.delete(_history_key(user_id))
    _local_history.pop(user_id, None)
    return {"deleted": user_id}


@app.get("/health", tags=["Operations"])
def health():
    redis = redis_status()
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "instance": settings.instance_id,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "storage": "redis" if redis["connected"] else "local-dev",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Application is starting")
    redis = redis_status()
    if not redis["connected"]:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "redis": redis},
        )
    return {"status": "ready", "redis": redis, "instance": settings.instance_id}


@app.get("/metrics", tags=["Operations"])
def metrics(_key_fingerprint: str = Depends(verify_api_key)):
    redis = redis_status()
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "storage": "redis" if redis["connected"] else "local-dev",
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "monthly_budget_usd": settings.monthly_budget_usd,
    }


def _handle_shutdown_signal(signum, _frame):
    logger.info(
        json.dumps({"event": "SIGTERM", "signal": signum, "action": "graceful_shutdown"}),
        extra={"event": "SIGTERM"},
    )
    raise SystemExit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
