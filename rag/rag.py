"""The RAG pipeline: retrieve the best chunks, then generate a cited answer.

Flow: question -> embed -> cosine search -> top-k chunks -> prompt with
numbered excerpts -> LLM answers citing [1], [2], ...

The min_score guard is a refusal mechanism: if even the best chunk is
dissimilar to the question, the document probably doesn't contain the
answer, and we say so instead of letting the model improvise.

Hybrid retrieval (hybrid=True) fuses vector similarity with keyword overlap
via Reciprocal Rank Fusion: chunks that match exact terms (e.g. "AMAZON.CA")
get a boost even when the embedding finds them only mildly similar. Unlike
a hard keyword pre-filter, fusion never vetoes — a paraphrased question with
no term overlap gracefully degrades to pure vector search.
"""
import re

from . import embeddings, llm, store

SYSTEM_RAG = """You answer questions using ONLY the excerpts below.
Rules:
- Cite every factual claim with the excerpt number, like [1] or [2].
- If the excerpts don't contain the answer, say so plainly. Do not use
  outside knowledge for facts, though you may explain terms in plain words.
- Keep answers short."""

STOPWORDS = frozenset(
    "a an the is are was were be been being what when where which who whom "
    "how why do does did done my your our their his her its in on at to "
    "for of and or it this that these those with by from as s t "
    "show me all list tell give find get much many".split()
)


def _terms(text: str) -> list[str]:
    """Lowercase alphanumeric tokens minus stopwords."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in STOPWORDS and len(w) > 1]


def keyword_scores(question: str, chunks: list[str]) -> list[tuple[int, int]]:
    """Distinct query terms found in each chunk: [(chunk_idx, overlap)]."""
    qterms = set(_terms(question))
    return [(idx, len(qterms & set(_terms(ch))))
            for idx, ch in enumerate(chunks)]


def hybrid_search(question: str, chunks: list[str], matrix, qvec,
                  top_k: int = 3, keyword_k: int = 10,
                  rrf_k: int = 60) -> tuple[list[tuple[int, float]], int]:
    """Fuse vector ranking and keyword ranking with Reciprocal Rank Fusion.

    score(chunk) = 1/(rrf_k + vector_rank) + 1/(rrf_k + keyword_rank)

    Returns ([(chunk_idx, vector_cosine_score)], kw_overlap_of_top_chunk).
    Scores stay as cosine similarities so the min_score gate keeps working;
    chunks surfaced only by keywords report their (low) vector score.
    """
    vec_hits = store.search(qvec, matrix, top_k=len(chunks))
    vec_score = dict(vec_hits)

    kw = keyword_scores(question, chunks)
    kw_ranked = [idx for idx, overlap in
                 sorted(kw, key=lambda p: p[1], reverse=True)
                 if overlap > 0][:keyword_k]

    fused: dict[int, float] = {}
    for rank, (idx, _) in enumerate(vec_hits):
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (rrf_k + rank + 1)
    for rank, idx in enumerate(kw_ranked):
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (rrf_k + rank + 1)

    top = sorted(fused, key=fused.get, reverse=True)[:top_k]
    top_kw_overlap = dict(kw).get(top[0], 0)
    return [(idx, vec_score.get(idx, 0.0)) for idx in top], top_kw_overlap


def _refusal(best_score: float) -> dict:
    return {
        "answer": ("I couldn't find anything relevant in the document "
                   f"(best match score {best_score:.2f})."),
        "hits": [],
        "chunks_used": [],
        "cost_usd": 0.0,
        "refused": True,
    }


def answer(question: str, chunks: list[str], matrix,
           top_k: int = 3, min_score: float = 0.25,
           hybrid: bool = False) -> dict:
    qvec = embeddings.embed_one(question)
    if hybrid:
        hits, kw_best = hybrid_search(question, chunks, matrix, qvec,
                                      top_k=top_k)
        best_idx, best_score = hits[0]
        # Refuse only if BOTH signals are weak: low vector similarity and
        # no keyword overlap in the top chunk.
        if best_score < min_score and kw_best == 0:
            return _refusal(best_score)
    else:
        hits = store.search(qvec, matrix, top_k=top_k)
        best_idx, best_score = hits[0]
        if best_score < min_score:
            return _refusal(best_score)

    context = "\n\n".join(
        f"[{rank}] {chunks[idx]}" for rank, (idx, _) in enumerate(hits, start=1)
    )
    user_prompt = (f"EXCERPTS:\n---\n{context}\n---\n\n"
                   f"QUESTION: {question}")
    resp = llm.ask(SYSTEM_RAG, user_prompt)
    return {
        "answer": resp["answer"],
        "hits": hits,
        "chunks_used": [idx for idx, _ in hits],
        "cost_usd": resp["cost_usd"],
        "input_tokens": resp["input_tokens"],
        "output_tokens": resp["output_tokens"],
        "refused": False,
    }


# ---- EXERCISES ----
# 1. [done via tune_threshold.py] Ask labeled answerable/unanswerable
#    questions, look at the top scores, pick a threshold that separates
#    them. Finding: the threshold is coupled to the chunk size.
# 2. [done above] Hybrid retrieval via Reciprocal Rank Fusion. Beats pure
#    vector search on exact-term questions ("AMAZON.CA"); degrades
#    gracefully to pure vector on paraphrases with no term overlap.
# 3. [done via rag_eval.py] Point prompt-lab at rag.answer() and measure
#    chunk-size variants. Add --repeat 3: single runs are noisy.
# 4. Paragraph-aware chunking: split on blank lines / headings instead of
#    fixed token windows, so tables and definitions never get cut mid-row.
