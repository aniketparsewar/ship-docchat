"""PDF text extraction (same approach as project 1)."""
import fitz  # PyMuPDF


def extract_text(pdf_path: str) -> tuple[str, int]:
    """Returns (full_text, page_count)."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    return "\n\n".join(pages), len(doc)
