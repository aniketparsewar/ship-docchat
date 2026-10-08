"""Service wrapper around the vendored Project 3 RAG pipeline.

Loads the vector store ONCE at startup (not per request — embedding the
question is per request, loading the matrix is not). Times every answer
so observability can report latency honestly.

Upload replaces the whole store: one document at a time. After ingest,
the in-memory chunks/matrix are reloaded so /ask serves the new doc
without a restart.
"""
import os
import time

from rag import chunker, costs, embeddings, pdf_reader, rag, store

STORE_DIR = os.getenv("STORE_DIR", "./store")
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.3"))
TOP_K = int(os.getenv("TOP_K", "3"))

_chunks: list[str] | None = None
_matrix = None


def load_store() -> tuple[int, bool]:
    """(Re)load chunks + matrix into memory. Returns (n_chunks, ok)."""
    global _chunks, _matrix
    try:
        _chunks, _matrix = store.load(STORE_DIR)
    except Exception:
        _chunks, _matrix = None, None
    return (len(_chunks) if _chunks else 0, _chunks is not None)


def store_ready() -> bool:
    return _chunks is not None


def ask_question(question: str, top_k: int = TOP_K) -> dict:
    """Run the RAG pipeline, timed. Raises RuntimeError if no store."""
    if not store_ready():
        raise RuntimeError(
            "No document ingested yet. POST a PDF to /upload first "
            "(or run python scripts/ingest.py)."
        )
    t0 = time.perf_counter()
    result = rag.answer(question, _chunks, _matrix,
                        top_k=top_k, min_score=MIN_SCORE, hybrid=True)
    latency_ms = (time.perf_counter() - t0) * 1000
    return {**result, "latency_ms": round(latency_ms, 1)}


def ingest_pdf(data: bytes) -> dict:
    """Extract -> paragraph-aware chunk -> embed -> save -> reload."""
    import fitz  # local import: only needed on the upload path

    doc = fitz.open(stream=data, filetype="pdf")
    pages = len(doc)
    text = "\n\n".join(page.get_text() for page in doc)

    chunks = chunker.chunk_paragraphs(text, chunk_tokens=500,
                                      overlap_blocks=1)
    total_tokens = sum(costs.count_tokens(c) for c in chunks)
    vectors = embeddings.embed(chunks)
    store.save(STORE_DIR, chunks, vectors)
    n, _ = load_store()
    return {
        "chunks": n,
        "pages": pages,
        "tokens_embedded": total_tokens,
        "embed_cost_usd": round(costs.estimate_embed_cost(total_tokens), 6),
    }
