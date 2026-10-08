# Deploying ShipDocChat

## Option A — Render (recommended)

1. Push this folder to a GitHub repo (root of the repo, so `render.yaml`
   and `Dockerfile` are at the top level).
2. In Render: **New → Blueprint**, point it at the repo. It reads
   `render.yaml` and creates the web service.
3. Set the secret env var `OPENAI_API_KEY` in the Render dashboard.
   `API_KEY` is auto-generated — copy it from the dashboard; that is the
   key you (and your users) put in the `X-API-Key` header / web UI.
4. Deploy. The first build takes a few minutes (`tiktoken` downloads its
   encoding at runtime on first request — that is normal).
5. Test:
   ```bash
   curl https://<your-service>.onrender.com/health
   curl -H "X-API-Key: <API_KEY>" -X POST \
     -F "file=@sample/sample-statement.pdf" \
     https://<your-service>.onrender.com/upload
   curl -H "X-API-Key: <API_KEY>" -H "Content-Type: application/json" \
     -d '{"question":"What is my new balance?"}' \
     https://<your-service>.onrender.com/ask
   ```

Notes:
- Render's free tier **sleeps after inactivity** — the first request after
  a pause takes ~30–60s to wake. `/health` is the wake-up call.
- The `./store` directory is **ephemeral** on Render: re-upload the PDF
  after each redeploy (or after a sleep-wake — uploads survive sleeps,
  not redeploys). A persistent disk or object storage is the production
  fix; it is a named stretch, not built here.

## Option B — Hugging Face Spaces (Docker)

1. Create a Space with the **Docker** SDK (blank template).
2. Push this folder's contents to the Space repo.
3. In Space **Settings → Variables and secrets**, add `OPENAI_API_KEY`
   (secret) and `API_KEY` (secret).
4. The Space builds the Dockerfile and serves on its public URL.

## Environment variables

| Var | Required | What |
|-----|----------|------|
| `OPENAI_API_KEY` | yes | embeddings + chat calls |
| `API_KEY` | yes | the single API key clients send as `X-API-Key` |
| `MIN_SCORE` | no | refusal threshold (default 0.3) |
| `TOP_K` | no | chunks retrieved per question (default 3) |
| `RATE_LIMIT_PER_MIN` | no | per-key requests/minute (default 30) |
| `STORE_DIR` | no | vector store dir (default ./store) |
| `PORT` | no | injected by the platform; default 8000 |
