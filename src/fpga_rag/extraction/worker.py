"""Document extraction worker for processing PDFs."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import track

from fpga_rag.config import settings
from fpga_rag.ingestion.manifest import ManifestRepository, ManifestStatus
from fpga_rag.utils.pdf import PDFPageText, extract_pdf_text_pages, get_pdf_metadata

console = Console()


@dataclass
class ExtractedDocument:
    """Container for fully extracted document."""

    doc_id: str
    version: str
    checksum: str
    page_count: int
    total_chars: int
    pages: list[PDFPageText]


class ExtractionWorker:
    """Worker that extracts text and metadata from PDF documents."""

    def __init__(self, manifest_repo: Optional[ManifestRepository] = None) -> None:
        self.manifest_repo = manifest_repo or ManifestRepository(settings.manifest_db_path)
        self.content_dir = settings.content_dir

    def process_document(self, pdf_path: Path, checksum: str) -> ExtractedDocument:
        """Extract all content from a PDF document.

        Args:
            pdf_path: Path to PDF file
            checksum: SHA256 checksum of the PDF

        Returns:
            ExtractedDocument with all extracted content

        This method:
        1. Updates manifest status to EXTRACTING
        2. Extracts text page-by-page (safe for large files)
        3. Saves extracted text to content/{doc_id}/{version}/text/
        4. Updates manifest status to INDEXING (ready for embedding)
        """
        console.print(f"[cyan]Processing: {pdf_path.name}[/cyan]")

        # Update status
        self.manifest_repo.update_status(checksum, ManifestStatus.EXTRACTING)

        # Get metadata
        metadata = get_pdf_metadata(pdf_path)
        console.print(f"  Doc ID: {metadata.doc_id}")
        console.print(f"  Version: {metadata.version}")
        console.print(f"  Pages: {metadata.page_count}")

        # Create output directory
        doc_content_dir = self.content_dir / metadata.doc_id / metadata.version
        text_dir = doc_content_dir / "text"
        text_dir.mkdir(parents=True, exist_ok=True)

        # Extract text page-by-page
        console.print("  Extracting text...")
        pages = extract_pdf_text_pages(pdf_path, text_dir)

        total_chars = sum(page.char_count for page in pages)
        console.print(f"  [green]✓ Extracted {len(pages)} pages ({total_chars:,} chars)[/green]")

        # Save consolidated metadata
        doc_metadata = {
            "doc_id": metadata.doc_id,
            "version": metadata.version,
            "checksum": checksum,
            "page_count": len(pages),
            "total_chars": total_chars,
            "source_file": pdf_path.name,
        }
        metadata_file = doc_content_dir / "metadata.json"
        metadata_file.write_text(json.dumps(doc_metadata, indent=2))

        # Save page index
        page_index = [
            {"page": p.page_number, "chars": p.char_count, "file": f"text/page_{p.page_number:04d}.txt"}
            for p in pages
        ]
        index_file = doc_content_dir / "page_index.json"
        index_file.write_text(json.dumps(page_index, indent=2))

        # Update status to ready for indexing
        self.manifest_repo.update_status(
            checksum,
            ManifestStatus.INDEXING,
            notes=f"Extracted {len(pages)} pages, {total_chars:,} chars"
        )

        return ExtractedDocument(
            doc_id=metadata.doc_id,
            version=metadata.version,
            checksum=checksum,
            page_count=len(pages),
            total_chars=total_chars,
            pages=pages,
        )

    def process_all_staged(self) -> list[ExtractedDocument]:
        """Process all documents in STAGED status.

        Returns:
            List of extracted documents
        """
        staged_docs = self.manifest_repo.list_by_status(ManifestStatus.STAGED)
        results = []

        for doc in track(list(staged_docs), description="Extracting documents"):
            # Find PDF file in incoming directory
            pdf_files = list(settings.incoming_dir.glob("*.pdf"))
            matching_pdf = None

            for pdf_file in pdf_files:
                # Match by checksum would be ideal, but for now match by doc_id pattern
                metadata = get_pdf_metadata(pdf_file)
                if metadata.doc_id == doc.doc_id and metadata.version == doc.version:
                    matching_pdf = pdf_file
                    break

            if not matching_pdf:
                console.print(f"[red]✗ Could not find PDF for {doc.doc_id}:{doc.version}[/red]")
                continue

            try:
                extracted = self.process_document(matching_pdf, doc.checksum)
                results.append(extracted)
            except Exception as e:
                console.print(f"[red]✗ Error processing {matching_pdf.name}: {e}[/red]")
                self.manifest_repo.update_status(
                    doc.checksum,
                    ManifestStatus.FAILED,
                    notes=f"Extraction failed: {str(e)}"
                )

        return results
