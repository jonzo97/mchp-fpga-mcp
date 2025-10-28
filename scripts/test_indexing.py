#!/usr/bin/env python
"""Test script for document indexing and search."""
from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fpga_rag.indexing import DocumentEmbedder
from fpga_rag.config import settings

console = Console()


def main() -> None:
    """Test indexing and search pipeline."""
    console.print("[bold cyan]Document Indexing & Search Test[/bold cyan]\n")

    # Configure paths
    fpga_mcp_root = Path.home() / "fpga_mcp"
    settings.content_dir = fpga_mcp_root / "content"
    settings.chroma_path = fpga_mcp_root / "chroma"

    # Step 1: Initialize embedder
    console.print("[yellow]Step 1: Initializing embedder...[/yellow]")
    embedder = DocumentEmbedder()

    if not embedder.vector_store.is_available():
        console.print("[red]✗ ChromaDB not available. Install with: pip install chromadb[/red]")
        return

    # Step 2: Clear old collection for fresh test
    console.print("\n[yellow]Step 2: Clearing old collection...[/yellow]")
    try:
        # Delete all documents (need to provide where clause or get all IDs)
        embedder.vector_store.collection.delete(where={})
        console.print("  [green]✓ Old collection cleared[/green]")
    except Exception as e:
        console.print(f"  [yellow]Warning: Could not clear collection: {e}[/yellow]")
        console.print(f"  [yellow]Attempting to delete collection and recreate...[/yellow]")
        try:
            embedder.vector_store.client.delete_collection(embedder.vector_store.collection_name)
            embedder.vector_store.collection = embedder.vector_store.client.get_or_create_collection(
                name=embedder.vector_store.collection_name
            )
            console.print("  [green]✓ Collection recreated[/green]")
        except Exception as e2:
            console.print(f"  [red]✗ Could not recreate: {e2}[/red]")

    # Step 3: Index all documents with NEW optimized chunking
    console.print("\n[yellow]Step 3: Indexing documents with semantic chunking...[/yellow]")
    total_chunks = embedder.index_all_documents(
        max_tokens=400,  # Safe limit (model max is 512, leave margin for special tokens)
        overlap_tokens=60,  # 15% overlap (NVIDIA optimal for technical docs)
        use_semantic=True  # Use semantic section-aware chunking
    )

    if total_chunks == 0:
        console.print("[red]No documents indexed[/red]")
        return

    # Step 4: Test search
    console.print("\n[yellow]Step 4: Testing search...[/yellow]\n")

    # Import search modules
    from mchp_mcp_core.storage.schemas import SearchQuery

    test_queries = [
        "DDR4 memory controller configuration",
        "PolarFire clocking resources CCC",
        "PCIe transceiver lanes",
        "FPGA power supply requirements",
        "GPIO pin configuration"
    ]

    for query_text in test_queries:
        console.print(f"\n[bold]Query:[/bold] \"{query_text}\"")

        query = SearchQuery(query=query_text, top_k=3)
        results = embedder.vector_store.search(query)

        if not results:
            console.print("  [dim]No results found[/dim]")
            continue

        for i, result in enumerate(results, 1):
            console.print(f"\n[cyan]{i}. {result.title} (Page {result.slide_or_page})[/cyan]")
            console.print(f"   Score: {result.score:.3f}")
            console.print(f"   {result.snippet[:150]}...")

    # Show collection stats
    console.print("\n[yellow]Collection Statistics:[/yellow]")
    info = embedder.vector_store.get_collection_info()
    console.print(f"  Collection: {info['name']}")
    console.print(f"  Total chunks: {info['points_count']}")
    console.print(f"  Path: {info['path']}")


if __name__ == "__main__":
    main()
