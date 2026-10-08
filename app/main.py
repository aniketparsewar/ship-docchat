"""ShipDocChat service: Project 3's RAG pipeline behind auth, guardrails,
and observability.

Run locally:
    uvicorn app.main:app --reload
"""
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

from . import auth, guardrails, observability, rag_service

app = FastAPI(title="ShipDocChat", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    n, ok = rag_service.load_store()
    print(f"Store: {n} chunks loaded." if ok else
          "Store: empty — POST a PDF to /upload or run scripts/ingest.py.")


class AskRequest(BaseModel):
    question: str
    top_k: int = 3


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "store_ready": rag_service.store_ready()}


@app.get("/")
def ui() -> FileResponse:
    return FileResponse(Path(__file__).parent.parent / "static" / "index.html")


@app.post("/upload")
async def upload(file: UploadFile = File(...),
                 api_key: str = Depends(auth.require_key)) -> dict:
    guardrails.check_rate_limit(api_key)
    t0 = time.perf_counter()
    data = await file.read()
    guardrails.check_pdf(data, file.filename or "upload.pdf")
    try:
        guardrails.check_page_count(rag_service.count_pdf_pages(data))
        result = rag_service.ingest_pdf(data)
    except HTTPException:
        raise  # 422 from check_page_count passes through untouched
    except Exception as e:  # e.g. corrupt PDF that passed magic bytes
        raise HTTPException(status_code=422,
                            detail=f"Could not parse PDF: {e}")
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    observability.log_event({
        "endpoint": "upload",
        "latency_ms": latency_ms,
        "pages": result["pages"],
        "chunks": result["chunks"],
        "cost_usd": result["embed_cost_usd"],
        "refused": False,
    })
    return {"ok": True, "latency_ms": latency_ms, **result}


@app.post("/ask")
async def ask(req: AskRequest,
              api_key: str = Depends(auth.require_key)) -> dict:
    guardrails.check_rate_limit(api_key)
    question = guardrails.check_question(req.question)
    top_k = max(1, min(req.top_k, 5))
    try:
        result = rag_service.ask_question(question, top_k=top_k)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    best_score = result["hits"][0][1] if result["hits"] else 0.0
    observability.log_event({
        "endpoint": "ask",
        "latency_ms": result["latency_ms"],
        "question": question,
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result["cost_usd"],
        "refused": result["refused"],
        "best_score": round(best_score, 3),
    })
    return {
        "answer": result["answer"],
        "citations": [idx for idx, _ in result["hits"]],
        "chunk_scores": [round(s, 3) for _, s in result["hits"]],
        "latency_ms": result["latency_ms"],
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": round(result["cost_usd"], 6),
        "refused": result["refused"],
    }


@app.get("/metrics")
def metrics(api_key: str = Depends(auth.require_key)) -> dict:
    guardrails.check_rate_limit(api_key)
    return observability.get_metrics()
