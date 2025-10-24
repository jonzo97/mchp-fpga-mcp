"""PDF metadata and extraction helpers."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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
    """Extract text from PDF page-by-page using pdftotext.

    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to store individual page text files

    Returns:
        List of PDFPageText objects with extracted text

    Note:
        This processes pages individually to avoid memory issues with large PDFs.
        Page text is also saved to {output_dir}/page_{N:04d}.txt for persistence.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pages: list[PDFPageText] = []

    page_count = get_pdf_page_count(pdf_path)
    if not page_count:
        # Fallback: extract all text at once
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                capture_output=True,
                text=True,
                check=True,
            )
            text = result.stdout
            pages.append(PDFPageText(page_number=1, text=text, char_count=len(text)))
        except subprocess.CalledProcessError:
            pass
        return pages

    # Extract page-by-page
    for page_num in range(1, page_count + 1):
        page_file = output_dir / f"page_{page_num:04d}.txt"

        try:
            # Extract single page
            result = subprocess.run(
                ["pdftotext", "-layout", "-f", str(page_num), "-l", str(page_num),
                 str(pdf_path), str(page_file)],
                capture_output=True,
                text=True,
                check=True,
            )

            # Read extracted text
            if page_file.exists():
                text = page_file.read_text(encoding="utf-8", errors="ignore")
                pages.append(PDFPageText(
                    page_number=page_num,
                    text=text,
                    char_count=len(text)
                ))
        except subprocess.CalledProcessError:
            # Create empty entry for failed pages
            pages.append(PDFPageText(page_number=page_num, text="", char_count=0))

    return pages
