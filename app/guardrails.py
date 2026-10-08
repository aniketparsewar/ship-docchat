"""Guardrails: validate untrusted input BEFORE it reaches the RAG pipeline.

- Upload: real PDF magic bytes, size cap, page cap.
- Ask: question length bounds.
- Rate limit: sliding window per API key, in memory.

Known demo-grade limit: the rate limiter is per-process memory. Two
replicas don't share it, so an attacker gets N x the limit with N
replicas. Production fix: a shared counter (Redis). The README says so.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_PAGES = 50
MAX_QUESTION_CHARS = 500

RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))

# key -> deque of request timestamps (monotonic seconds)
_hits: dict[str, deque] = defaultdict(deque)


def check_rate_limit(api_key: str) -> None:
    now = time.monotonic()
    window = _hits[api_key]
    while window and window[0] <= now - 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {RATE_LIMIT_PER_MIN}/min per key.",
            headers={"Retry-After": "60"},
        )
    window.append(now)


def check_pdf(data: bytes, filename: str) -> None:
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(data)} bytes "
                   f"(max {MAX_UPLOAD_BYTES}).",
        )
    # Magic bytes, not the extension: a renamed .exe must not pass.
    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=422,
            detail=f"{filename!r} is not a PDF (bad magic bytes).",
        )


def check_page_count(pages: int) -> None:
    if pages > MAX_PAGES:
        raise HTTPException(
            status_code=422,
            detail=f"PDF has {pages} pages (max {MAX_PAGES}).",
        )


def check_question(question: str) -> str:
    q = question.strip()
    if not q:
        raise HTTPException(status_code=422, detail="Question is empty.")
    if len(q) > MAX_QUESTION_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Question is {len(q)} chars (max {MAX_QUESTION_CHARS}).",
        )
    return q
