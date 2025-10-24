#!/usr/bin/env python
"""Test script for PDF extraction pipeline."""
from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fpga_rag.extraction import ExtractionWorker
from fpga_rag.ingestion import IngestionOrchestrator

console = Console()


def main() -> None:
    """Test the extraction pipeline on a small PDF."""
    console.print("[bold cyan]PDF Extraction Pipeline Test[/bold cyan]\n")

    # Step 1: Stage a document
    console.print("[yellow]Step 1: Staging document...[/yellow]")
    orchestrator = IngestionOrchestrator()

    # Find the smallest PDF for testing
    pdf_dir = Path.home() / "fpga_mcp"
    test_pdf = pdf_dir / "PolarFire_FPGA_Board_Design_UG0726_V11.pdf"

    if not test_pdf.exists():
        console.print(f"[red]✗ Test PDF not found: {test_pdf}[/red]")
        return

    # Temporarily set incoming dir to fpga_mcp root
    from fpga_rag.config import settings
    settings.incoming_dir = pdf_dir
    settings.content_dir = pdf_dir / "content"
    settings.manifest_db_path = pdf_dir / "manifest.db"

    jobs = list(orchestrator.stage_from_directory())
    console.print(f"[green]✓ Staged {len(jobs)} document(s)[/green]\n")

    # Step 2: Extract text
    console.print("[yellow]Step 2: Extracting text...[/yellow]")
    worker = ExtractionWorker()

    extracted_docs = worker.process_all_staged()
    console.print(f"\n[green]✓ Successfully extracted {len(extracted_docs)} document(s)[/green]\n")

    # Step 3: Show results
    for doc in extracted_docs:
        console.print(f"[bold]Document: {doc.doc_id} ({doc.version})[/bold]")
        console.print(f"  Pages: {doc.page_count}")
        console.print(f"  Total characters: {doc.total_chars:,}")
        console.print(f"  Checksum: {doc.checksum[:16]}...")

        # Show sample from first page with content
        for page in doc.pages:
            if page.char_count > 100:
                sample = page.text[:200].replace("\n", " ").strip()
                console.print(f"\n[dim]Sample from page {page.page_number}:[/dim]")
                console.print(f"[dim]{sample}...[/dim]\n")
                break

    # Show output directory structure
    console.print("[yellow]Output directory structure:[/yellow]")
    content_dir = settings.content_dir
    if content_dir.exists():
        import subprocess
        result = subprocess.run(
            ["tree", "-L", "3", str(content_dir)],
            capture_output=True,
            text=True,
        )
        console.print(result.stdout)


if __name__ == "__main__":
    main()
