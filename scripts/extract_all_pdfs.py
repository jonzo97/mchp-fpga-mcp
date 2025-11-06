#!/usr/bin/env python3
"""Extract all PDFs in the fpga_mcp root directory."""
from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fpga_rag.extraction import ExtractionWorker
from fpga_rag.ingestion import IngestionOrchestrator
from fpga_rag.config import settings

console = Console()


def main() -> None:
    """Extract all PDFs from fpga_mcp root directory."""
    console.print("[bold cyan]PDF Extraction - All Documents[/bold cyan]\n")

    # Configure paths
    fpga_mcp_root = Path.home() / "fpga_mcp"
    settings.incoming_dir = fpga_mcp_root
    settings.content_dir = fpga_mcp_root / "content"
    settings.manifest_db_path = fpga_mcp_root / "manifest.db"

    console.print(f"[yellow]Source:[/yellow] {fpga_mcp_root}")
    console.print(f"[yellow]Output:[/yellow] {settings.content_dir}\n")

    # Step 1: Stage all documents
    console.print("[yellow]Step 1: Staging documents...[/yellow]")
    orchestrator = IngestionOrchestrator()
    jobs = list(orchestrator.stage_from_directory())

    if not jobs:
        console.print("[green]✓ All PDFs already extracted[/green]")
        return

    console.print(f"[green]✓ Found {len(jobs)} new PDF(s) to extract[/green]\n")

    # Step 2: Extract all staged documents
    console.print("[yellow]Step 2: Extracting text from PDFs...[/yellow]")
    worker = ExtractionWorker()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting...", total=None)
        extracted_docs = worker.process_all_staged()
        progress.update(task, completed=True)

    console.print(f"\n[green]✓ Successfully extracted {len(extracted_docs)} document(s)[/green]\n")

    # Step 3: Show extraction results
    total_pages = 0
    total_chars = 0

    for doc in extracted_docs:
        console.print(f"[bold]{doc.doc_id}[/bold] (v{doc.version})")
        console.print(f"  Pages: {doc.page_count:,}")
        console.print(f"  Characters: {doc.total_chars:,}")
        total_pages += doc.page_count
        total_chars += doc.total_chars

    console.print(f"\n[bold cyan]Total:[/bold cyan]")
    console.print(f"  Documents: {len(extracted_docs)}")
    console.print(f"  Pages: {total_pages:,}")
    console.print(f"  Characters: {total_chars:,}")


if __name__ == "__main__":
    main()
