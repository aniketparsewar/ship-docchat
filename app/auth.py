"""API-key auth. Demo-grade: one shared key, no rotation, no per-user keys.

The key comes from the API_KEY env var and is compared with
secrets.compare_digest (constant-time) so response timing doesn't leak
how close a guess was. /health stays open so load balancers and
uptime checks don't need a secret.
"""
import os
import secrets

from fastapi import Header, HTTPException


def _expected_key() -> str:
    key = os.getenv("API_KEY", "")
    if not key:
        raise RuntimeError(
            "API_KEY is not set. Generate one with "
            "`python -c \"import secrets; print(secrets.token_hex(32))\"` "
            "and put it in .env (or the platform's env vars)."
        )
    return key


async def require_key(x_api_key: str = Header(default="")) -> str:
    if not x_api_key or not secrets.compare_digest(x_api_key, _expected_key()):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Send it as X-API-Key.",
        )
    return x_api_key
