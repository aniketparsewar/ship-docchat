#!/usr/bin/env python3
"""Ingest the bundled sample PDF into ./store (one-time local setup).

Usage:
    python scripts/ingest.py [--pdf path/to/file.pdf] [--store ./store]

For other PDFs in production, POST them to /upload instead.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app import rag_service  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default="sample/sample-statement.pdf")
    parser.add_argument("--store", default="./store")
    args = parser.parse_args()

    import os
    os.environ["STORE_DIR"] = args.store
    # Re-read env after overriding (module read it at import).
    rag_service.STORE_DIR = args.store

    data = Path(args.pdf).read_bytes()
    print(f"Read {len(data)} bytes from {args.pdf}")
    result = rag_service.ingest_pdf(data)
    print(f"Ingested {result['chunks']} chunks from {result['pages']} pages "
          f"(~${result['embed_cost_usd']:.4f} embedding cost).")
    print("Start the service with: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
