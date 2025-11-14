"""PDF metadata and extraction helpers.

Now uses mchp-mcp-core for enhanced extraction (tables, structure awareness).
Maintains backward compatibility with existing ExtractionWorker API.
"""
from __future__ import annotations

import re
import subprocess  # Still used by get_pdf_page_count() for lightweight metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mchp_mcp_core.extractors import PDFExtractor as CorePDFExtractor
from mchp_mcp_core.models import ExtractedChunk


@dataclass
class PDFMetadata:
    """Normalized metadata about a PDF suitable for manifest creation."""

    doc_id: str
    version: str
    size_bytes: int
    page_count: int | None = None
    source_url: str | None = None
    notes: str | None = None


@dataclass
class PDFPageText:
    """Extracted text for a single PDF page."""

    page_number: int
    text: str
    char_count: int


DEFAULT_DOC_ID = "unknown_doc"
DEFAULT_VERSION = "unknown_version"


def parse_doc_id(path: Path) -> tuple[str, str]:
    """Infer doc id and version from filename convention.

    Example: "PolarFire_FPGA_Board_Design_UG0726_V11.pdf"
             -> ("PolarFire", "V11")
    """
    stem = path.stem
    # Try to extract version from common patterns (V11, VB, etc.)
    version_match = re.search(r"_(V[A-Z0-9]+)$", stem)
    if version_match:
        version = version_match.group(1)
        doc_id = stem[:version_match.start()].replace("_", " ")
    else:
        parts = stem.split("_")
        doc_id = " ".join(parts[:-1]) if len(parts) > 1 else stem
        version = parts[-1] if len(parts) > 1 else DEFAULT_VERSION

    return doc_id, version


def get_pdf_page_count(path: Path) -> Optional[int]:
    """Get page count using pdfinfo command."""
    try:
        result = subprocess.run(
            ["pdfinfo", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("Pages:"):
                return int(line.split(":")[1].strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return None
    return None


def get_pdf_metadata(path: Path) -> PDFMetadata:
    """Extract metadata from PDF using pdfinfo."""
    doc_id, version = parse_doc_id(path)
    size_bytes = path.stat().st_size
    page_count = get_pdf_page_count(path)

    return PDFMetadata(
        doc_id=doc_id,
        version=version,
        size_bytes=size_bytes,
        page_count=page_count,
    )


def extract_pdf_text_pages(pdf_path: Path, output_dir: Path) -> list[PDFPageText]:
    """Extract text from PDF page-by-page using mchp-mcp-core.

    Now uses mchp-mcp-core's CorePDFExtractor for enhanced extraction including:
    - Multi-strategy table extraction (3-way consensus)
    - Structure-aware chunking (section hierarchy)
    - Specification extraction (electrical parameters)

    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to store individual page text files

    Returns:
        List of PDFPageText objects with extracted text

    Note:
        This maintains backward compatibility with the original API.
        Page text is saved to {output_dir}/page_{N:04d}.txt for persistence.
        Tables are included inline in the text content.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize mchp-mcp-core extractor
    extractor = CorePDFExtractor(config={
        'chunk_size': 10000,  # Large chunks to preserve page boundaries
        'overlap': 0,
        'preserve_sections': True,
        'extract_images': False,
        'chunking_strategy': 'fixed',
        'min_chunk_size': 100,
        'max_chunk_size': 20000,
    })

    # Extract using core infrastructure
    doc_id, _ = parse_doc_id(pdf_path)
    chunks = extractor.extract_document(str(pdf_path), document_id=doc_id)

    # Group chunks by page number
    pages_dict: dict[int, list[str]] = {}
    for chunk in chunks:
        page_num = chunk.page_start  # ExtractedChunk uses 1-indexed pages

        if page_num not in pages_dict:
            pages_dict[page_num] = []

        # Add chunk content
        if chunk.chunk_type == "text":
            pages_dict[page_num].append(chunk.content)
        elif chunk.chunk_type == "table":
            # Table content is already formatted as markdown by mchp-mcp-core
            # Include it with clear markers for downstream processing
            caption = chunk.metadata.get("caption", f"Table {chunk.metadata.get('table_index', '')}")
            pages_dict[page_num].append(f"\n[TABLE: {caption}]\n{chunk.content}\n[/TABLE]\n")

    # Convert to PDFPageText format and save individual files
    pages: list[PDFPageText] = []
    for page_num in sorted(pages_dict.keys()):
        # Combine all content for this page
        text = "\n\n".join(pages_dict[page_num])
        char_count = len(text)

        # Save to individual page file (maintain compatibility)
        page_file = output_dir / f"page_{page_num:04d}.txt"
        page_file.write_text(text, encoding="utf-8")

        pages.append(PDFPageText(
            page_number=page_num,
            text=text,
            char_count=char_count
        ))

    return pages
