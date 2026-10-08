"""Token counting and cost estimates (gpt-4o-mini + text-embedding-3-small)."""
import tiktoken

ENCODING = "o200k_base"

LLM_INPUT_PER_1M = 0.15
LLM_OUTPUT_PER_1M = 0.60
EMBED_PER_1M = 0.02


def count_tokens(text: str) -> int:
    enc = tiktoken.get_encoding(ENCODING)
    return len(enc.encode(text))


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return ((input_tokens / 1e6) * LLM_INPUT_PER_1M
            + (output_tokens / 1e6) * LLM_OUTPUT_PER_1M)


def estimate_embed_cost(total_tokens: int) -> float:
    return (total_tokens / 1e6) * EMBED_PER_1M
