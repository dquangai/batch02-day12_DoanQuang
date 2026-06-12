"""API-key authentication dependency."""
from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(x_api_key: str | None = Security(_api_key_header)) -> str:
    """Validate X-API-Key and return a non-secret key fingerprint."""
    expected = settings.agent_api_key
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Send a valid X-API-Key header.",
        )
    return hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()[:16]
