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

- **Validate before you spend.** Every guardrail (PDF magic bytes, 10MB cap, 50-page cap, 500-char question cap) runs before the first embedding call, because the first API call is the first cent. A 552-char question gets a 422 having cost me $0.
- **Your dashboard can lie by omission.** My /metrics showed a perfectly healthy request while the answer silently dropped a transaction. Latency, cost, and refusal rate measure the operation, not the answer — correctness needs evals, not just metrics. I found out when a Project 3 flake recurred in production.
- **401/422/429s are invisible to my own metrics.** Guardrail rejections raise before the logger runs, so refusal_rate only counts RAG refusals. A perimeter on fire looks like a quiet dashboard.
- **Metrics don't survive a restart.** The aggregates lived in memory; the JSONL log was the durable truth. I added replay() at startup — 60 requests survived a restart afterward. (Measured at n=60: p50 1025ms, p95 2144ms, ~$0.16 per 1,000 questions.)
- **Untested paths are broken paths.** The upload endpoint was broken since Day 1 and nobody noticed — every test ran against the pre-ingested store. Worse, a broad except-Exception → 422 disguised the server bug as "your PDF is bad." Client errors for bad input, 5xx for my bugs.
- **"Works on my machine" dies at the Docker build.** I fixed a missing dependency locally with pip install; production failed with the same import error because it wasn't in requirements.txt. The container is the first honest environment.
- **Async doesn't mean concurrent.** My async endpoint called blocking sync ingest, so uploads serialized and every other request hung during an upload. The damage was starvation, not corruption — run_in_threadpool is the fix.
- **Per-process state breaks under replicas.** 60 req/min across 2 replicas = 30 each, zero 429s — each limiter under-counts with its partial view (Redis is the fix). Per-replica disks diverge the store too (shared backend + cache invalidation).
- **Cap the blast radius, not just the speed.** 30/min limits velocity; a leaked key at 30/min all day is ~43,000 requests of my money. I added a $1.00/day rolling budget per key — the backstop the rate limiter isn't.
- **Thresholds are coupled to chunking.** Re-ingesting with ~500-token chunks (vs ~50) silently shifted what my min-score gate means. Learned it in Project 3, re-learned it in production.
- **Production is a different computer.** Dashboard secrets instead of .env, PORT injected by the platform, ephemeral disk (re-upload after every redeploy), free tier sleeps (30–60s cold start; /health wakes it).

