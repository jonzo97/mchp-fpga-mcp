"""PDF metadata helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PDFMetadata:
    """Normalized metadata about a PDF suitable for manifest creation."""

    doc_id: str
    version: str
    size_bytes: int
    page_count: int | None = None
    source_url: str | None = None
    notes: str | None = None


DEFAULT_DOC_ID = "unknown_doc"
DEFAULT_VERSION = "unknown_version"


def parse_doc_id(path: Path) -> tuple[str, str]:
    """Infer doc id and version from filename convention."""

    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return DEFAULT_DOC_ID, DEFAULT_VERSION


def get_pdf_metadata(path: Path) -> PDFMetadata:
    """Placeholder that infers metadata from filename and file stats.

    Replace with pdfinfo/doctr-powered extraction as pipeline matures.
    """

    doc_id, version = parse_doc_id(path)
    size_bytes = path.stat().st_size
    return PDFMetadata(
        doc_id=doc_id,
        version=version,
        size_bytes=size_bytes,
    )
