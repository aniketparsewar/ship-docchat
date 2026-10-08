"""Turn text into embedding vectors via the OpenAI API.

An embedding is a list of ~1536 numbers that captures the *meaning* of the
text: similar meanings -> nearby vectors. Retrieval = "find the chunks whose
vectors point in the same direction as the question's vector".
"""
from . import config

BATCH_SIZE = 100  # API accepts up to 2048 inputs per request; 100 is safe


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns one vector per input, in order."""
    client = config.get_client()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        resp = client.embeddings.create(
            model=config.EMBEDDING_MODEL,
            input=batch,
        )
        # The API returns them in order; sort defensively by index.
        ordered = sorted(resp.data, key=lambda d: d.index)
        vectors.extend(d.embedding for d in ordered)
    return vectors


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
