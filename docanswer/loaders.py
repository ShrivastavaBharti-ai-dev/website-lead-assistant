"""Turn PDF, Word and text files into `Page` objects with citable locations."""
from __future__ import annotations

import io
import re
from pathlib import Path

from .types import Page

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

_WS = re.compile(r"[ \t ]+")


def _clean(text: str) -> str:
    """Normalise whitespace but keep paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # PDF extraction often breaks words across lines with a hyphen.
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    lines = [_WS.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_pdf(data: bytes, source: str) -> list[Page]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = _clean(page.extract_text() or "")
        if text:
            pages.append(Page(text=text, source=source, location=f"p. {number}"))
    return pages


def load_docx(data: bytes, source: str) -> list[Page]:
    """Word files have no fixed pages, so each heading starts a new section."""
    from docx import Document

    from docx.table import Table

    doc = Document(io.BytesIO(data))
    sections: list[tuple[str, list[str]]] = [("Introduction", [])]
    # Walk paragraphs and tables in document order so a table stays in the
    # section it was written under (e.g. a product-code table).
    for block in doc.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                line = " | ".join(cell.text.strip() for cell in row.cells)
                if line.strip(" |"):
                    sections[-1][1].append(line)
            continue
        text = block.text.strip()
        if not text:
            continue
        style = (block.style.name or "").lower() if block.style is not None else ""
        if style.startswith("heading") or style == "title":
            sections.append((text, []))
        else:
            sections[-1][1].append(text)
    return [
        Page(text=_clean("\n".join(lines)), source=source, location=f"Section: {title}")
        for title, lines in sections
        if lines
    ]


def load_text(data: bytes, source: str) -> list[Page]:
    """Plain text / Markdown, split on Markdown headings when present."""
    text = data.decode("utf-8", errors="replace")
    parts = re.split(r"^(#{1,6} .+)$", text, flags=re.MULTILINE)
    if len(parts) == 1:
        cleaned = _clean(text)
        return [Page(text=cleaned, source=source, location="Document")] if cleaned else []
    pages = []
    if _clean(parts[0]):
        pages.append(Page(text=_clean(parts[0]), source=source, location="Introduction"))
    for heading, body in zip(parts[1::2], parts[2::2]):
        cleaned = _clean(body)
        if cleaned:
            title = heading.lstrip("#").strip()
            pages.append(Page(text=cleaned, source=source, location=f"Section: {title}"))
    return pages


def load_bytes(data: bytes, filename: str) -> list[Page]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return load_pdf(data, filename)
    if ext == ".docx":
        return load_docx(data, filename)
    if ext in {".txt", ".md"}:
        return load_text(data, filename)
    raise ValueError(f"Unsupported file type: {filename} (use PDF, DOCX, TXT or MD)")


def load_paths(paths: list[str | Path]) -> list[Page]:
    pages: list[Page] = []
    for path in paths:
        path = Path(path)
        pages.extend(load_bytes(path.read_bytes(), path.name))
    return pages


def load_folder(folder: str | Path) -> list[Page]:
    files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)
    return load_paths(files)
