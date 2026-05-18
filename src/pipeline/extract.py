"""File extraction: PDF, DOCX, TXT → raw text with structural cleanup."""

import os
import tempfile
from pathlib import Path
from typing import Optional

from docx import Document as DocxDocument
from pypdf import PdfReader


class ExtractionError(Exception):
    pass


def extract_text(file_path: str | Path, mime_type: Optional[str] = None) -> str:
    """Extract text from PDF, DOCX, or TXT with structural cleanup."""
    path = Path(file_path)
    if not path.exists():
        raise ExtractionError(f"File not found: {file_path}")

    # Guard against very large files that could OOM the container (fix #12)
    max_bytes = 10 * 1024 * 1024  # 10 MB
    file_size = path.stat().st_size
    if file_size > max_bytes:
        raise ExtractionError(
            f"File '{path.name}' is {file_size // (1024*1024):.1f} MB — "
            f"maximum supported size is 10 MB. Please split the document and re-upload."
        )

    inferred = mime_type or _infer_type(path)
    text = ""

    try:
        if inferred == "application/pdf":
            text = _extract_pdf(path)
        elif inferred in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ):
            text = _extract_docx(path)
        elif inferred == "text/plain":
            text = _extract_txt(path)
        else:
            raise ExtractionError(f"Unsupported file type: {inferred}")
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Failed to extract {path.name}: {e}")

    return text.strip()


def _infer_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    elif ext in (".docx", ".doc"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif ext == ".txt":
        return "text/plain"
    elif ext in (".md", ".markdown"):
        return "text/plain"
    return "application/octet-stream"


def _extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    lines = []
    for page in reader.pages:
        page_text = page.extract_text()
        if not page_text:
            continue
        for line in page_text.split("\n"):
            cleaned = line.strip()
            if cleaned:
                lines.append(cleaned)
        lines.append("")
    return "\n".join(lines)


_TOC_STYLES = {"toc 2", "toc 3", "toc 4", "toc 5", "toc 6"}


def _extract_docx(path: Path) -> str:
    from docx.text.paragraph import Paragraph as DocxParagraph
    from docx.table import Table as DocxTable

    doc = DocxDocument(str(path))
    parts = []

    for child in doc.element.body.iterchildren():
        tag = child.tag.split("}")[-1]

        if tag == "p":
            para = DocxParagraph(child, doc)
            style = para.style.name if para.style else ""
            if style in _TOC_STYLES:
                continue
            text = para.text.strip()
            if not text:
                continue
            if style.startswith("Heading"):
                try:
                    level = int(style.split()[-1])
                    prefix = "#" * min(level, 4) + " "
                except (ValueError, IndexError):
                    prefix = "## "
                parts.append(prefix + text)
            elif "List" in style:
                parts.append("- " + text)
            else:
                parts.append(text)

        elif tag == "tbl":
            table = DocxTable(child, doc)
            for row in table.rows:
                seen = set()
                cells = []
                for cell in row.cells:
                    cid = id(cell._tc)
                    if cid not in seen:
                        seen.add(cid)
                        cells.append(cell.text.strip().replace("\n", " "))
                if any(cells):
                    parts.append(" | ".join(cells))

    return "\n".join(parts)


def _extract_txt(path: Path) -> str:
    encodings = ["utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            return open(path, "r", encoding=enc).read()
        except UnicodeDecodeError:
            continue
    raise ExtractionError(f"Could not decode {path.name} with any known encoding")


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[dict]:
    """Split text into overlapping chunks with context headers."""
    if not text.strip():
        return []

    lines = text.split("\n")
    chunks = []
    start = 0
    chunk_num = 0

    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]

        first_line = chunk_text.split("\n")[0][:100]
        chunks.append(
            {
                "chunk_id": f"chunk-{chunk_num:04d}",
                "text": chunk_text,
                "char_start": start,
                "char_end": end,
                "preview": first_line,
            }
        )

        start += chunk_size - overlap
        chunk_num += 1

    return chunks


def save_upload(upload_file, destination: Path) -> Path:
    """Save an uploaded file to a destination path."""
    with open(destination, "wb") as f:
        f.write(upload_file.read())
    return destination