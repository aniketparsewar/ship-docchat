"""Split text into overlapping token windows.

Why chunk at all? Two reasons:
1. Embedding models have input limits, and one giant vector for a whole
   document is a blurry summary — retrieval needs focused units.
2. The LLM's context window is finite — we can only afford to send the
   most relevant chunks, not the whole document.

Overlap exists so a sentence split across a boundary still appears whole
in at least one chunk.

Two strategies:
- chunk_text: fixed token windows (fast, but can cut mid-sentence/row).
- chunk_paragraphs: split into structural blocks first (blank lines and
  headings), then pack whole blocks into token windows. A boundary never
  lands mid-line, so tables and definitions stay intact.
"""
import re

import tiktoken

ENCODING = "o200k_base"


def chunk_text(text: str, chunk_tokens: int = 500,
               overlap_tokens: int = 50) -> list[str]:
    enc = tiktoken.get_encoding(ENCODING)
    tokens = enc.encode(text)
    if not tokens:
        return []
    chunks = []
    step = chunk_tokens - overlap_tokens
    start = 0
    while start < len(tokens):
        end = start + chunk_tokens
        chunks.append(enc.decode(tokens[start:end]))
        if end >= len(tokens):
            break
        start += step
    return chunks


def _is_heading(line: str) -> bool:
    """ALL-CAPS short line with no dollar amount: a section heading, not
    a shouting transaction row (those contain '$')."""
    s = line.strip()
    return (bool(s) and s.isupper() and len(s) < 60 and "$" not in s)


def _blocks(text: str) -> list[str]:
    """Split text into structural blocks: blank lines always break, and
    headings start a new block so they stay glued to their content."""
    blocks, current = [], []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        if _is_heading(line) and current:
            blocks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _pack(units: list[str], chunk_tokens: int,
          overlap_units: int) -> list[str]:
    """Greedily pack atomic `units` into token windows.

    Units are never split; overlap is whole units carried forward. A unit
    larger than the budget is hard-split as a last resort.
    """
    enc = tiktoken.get_encoding(ENCODING)
    chunks, current, current_toks = [], [], 0
    for unit in units:
        utoks = len(enc.encode(unit))
        if utoks > chunk_tokens:
            if current:
                chunks.append("\n\n".join(current))
            chunks.extend(chunk_text(unit, chunk_tokens, overlap_tokens=0))
            current, current_toks = [], 0
            continue
        if current and current_toks + utoks > chunk_tokens:
            chunks.append("\n\n".join(current))
            current = current[-overlap_units:] if overlap_units else []
            current_toks = sum(len(enc.encode(u)) for u in current)
        current.append(unit)
        current_toks += utoks
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_paragraphs(text: str, chunk_tokens: int = 500,
                     overlap_blocks: int = 1) -> list[str]:
    """Paragraph-aware chunking: structural blocks packed into token windows.

    Block boundaries are blank lines and headings, so a chunk boundary
    never cuts a line in half. A block larger than the budget is split
    into individual lines (still never mid-line); only a single line
    larger than the budget is hard-split, as a last resort.
    """
    enc = tiktoken.get_encoding(ENCODING)
    units: list[str] = []
    for block in _blocks(text):
        if len(enc.encode(block)) > chunk_tokens:
            units.extend(l for l in block.split("\n") if l.strip())
        else:
            units.append(block)
    return _pack(units, chunk_tokens, overlap_blocks)


# ---- EXERCISES ----
# 1. Try chunk_tokens=200 vs 1000 on your statement. Which retrieves better?
#    (Hint: point your prompt-lab harness at this pipeline to measure it.)
# 2. [done above] Paragraph-aware chunking: split into structural blocks
#    (blank lines + headings), pack whole blocks into token windows.
#    Measure it against fixed windows with rag_eval.py --repeat 3.
# 3. Add chunk metadata: page numbers. Requires tracking token->page offsets
#    in pdf_reader — how would you do it?
