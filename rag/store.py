"""A minimal vector store: numpy arrays on disk, cosine similarity for search.

This is deliberately hand-rolled, not ChromaDB — the whole point is to see
that a "vector database" is, at its core, a matrix plus a similarity
function. (Stretch exercise: swap this for Chroma and compare.)

Cosine similarity = (a.b) / (|a||b|). It measures the *angle* between
vectors, ignoring magnitude: 1.0 = same direction (same meaning),
0.0 = unrelated.
"""
import json
from pathlib import Path

import numpy as np

CHUNKS_FILE = "chunks.json"
VECTORS_FILE = "vectors.npz"


def save(store_dir: str, chunks: list[str], vectors: list[list[float]]) -> None:
    path = Path(store_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / CHUNKS_FILE).write_text(json.dumps(chunks, ensure_ascii=False),
                                    encoding="utf-8")
    np.savez_compressed(path / VECTORS_FILE,
                        vectors=np.array(vectors, dtype=np.float32))
    print(f"Saved {len(chunks)} chunks to {store_dir}/")


def load(store_dir: str) -> tuple[list[str], np.ndarray]:
    path = Path(store_dir)
    chunks = json.loads((path / CHUNKS_FILE).read_text(encoding="utf-8"))
    matrix = np.load(path / VECTORS_FILE)["vectors"]
    return chunks, matrix


def search(query_vector: list[float], matrix: np.ndarray,
           top_k: int = 3) -> list[tuple[int, float]]:
    """Returns [(chunk_index, cosine_similarity)] sorted best-first."""
    q = np.array(query_vector, dtype=np.float32)
    q_norm = q / np.linalg.norm(q)
    m_norm = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    sims = m_norm @ q_norm  # cosine similarity against every chunk at once
    best = np.argsort(sims)[::-1][:top_k]
    return [(int(i), float(sims[i])) for i in best]


# ---- EXERCISES ----
# 1. Time search() on 10k fake vectors. At what scale does brute force hurt?
#    (That's the problem ANN indexes like HNSW solve — now you know why
#    real vector DBs exist.)
# 2. Add a metadata filter: search only chunks from certain pages.
# 3. STRETCH: replace this file's internals with chromadb, keeping the
#    save/load/search function signatures identical.
