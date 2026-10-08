# ShipDocChat — Project 3's RAG chatbot, deployed

A real web service around the Project 3 DocChat RAG pipeline: API-key auth,
upload-a-PDF ingestion, cited answers, per-request latency/cost logging, a
`/metrics` dashboard endpoint, guardrails (file validation, question
limits, rate limiting, server-side refusal), and Docker + Render deployment.

The RAG core (`rag/`) is vendored unchanged from Project 3 — this project
is about everything *around* the model: the difference between a pipeline
that scores 6/6 locally and a service you can hand someone a URL to.

> **Demo data honesty note:** the bundled document is the *fictional*
> Nebula Bank sample statement generated for testing. Answers cite a
> made-up fixture, not real financial data.

## Quickstart (local)

```bash
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY, generate API_KEY (see below)
python scripts/ingest.py
uvicorn app.main:app --reload
# open http://127.0.0.1:8000
```

Generate an API key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Endpoints

| Method | Path      | Auth | What it does |
|--------|-----------|------|--------------|
| GET    | `/health` | no   | liveness + whether a store is loaded |
| POST   | `/upload` | key  | ingest a PDF (≤10MB, ≤50 pages, must be a real PDF) |
| POST   | `/ask`    | key  | `{"question": "..."}` → answer, citations, latency_ms, tokens, cost_usd, refused |
| GET    | `/metrics`| key  | request counts, p50/p95 latency, token/cost totals, refusal rate |
| GET    | `/`       | no   | minimal web UI (paste your API key to use it) |

Auth: `X-API-Key: <your key>` header. Rate limit: 30 req/min per key
(tune via `RATE_LIMIT_PER_MIN`).

## Deploy

See `DEPLOY.md` (Render via `render.yaml`, plus a Hugging Face Spaces
alternative).

## Known demo-grade limits (not hidden)

- Single shared API key — no per-user keys, rotation, or OAuth.
- Rate limiter is per-process memory; it does not coordinate across
  replicas (production fix: Redis).
- Request log records full question text — fine for a personal demo,
  PII-scrub before any multi-user use.
- Upload replaces the whole store (one document at a time).

## What I learned

- *(fill in after the project closes — Day 4 quiz first)*
