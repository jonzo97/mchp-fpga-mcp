"""Document embedding and indexing using mchp-mcp-core."""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Add mchp-mcp-core to path
MCHP_CORE_PATH = Path.home() / "mchp-mcp-core"
if str(MCHP_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(MCHP_CORE_PATH))

from mchp_mcp_core.embeddings.sentence_transformers import EmbeddingModel
from mchp_mcp_core.storage.chromadb import ChromaDBVectorStore as _ChromaDBVectorStore
from mchp_mcp_core.storage.schemas import DocumentChunk
from rich.console import Console
from rich.progress import track

from fpga_rag.config import settings


class ChromaDBVectorStore(_ChromaDBVectorStore):
    """Wrapper around ChromaDB that filters metadata to remove lists/dicts."""

    def add_documents(self, chunks, batch_size=100, show_progress=True):
        """Override to filter metadata before adding."""
        if not self.available or not chunks:
            return 0, 0

        # Prepare data manually with filtered metadata
        ids = [f"{chunk.doc_id}_{chunk.slide_or_page}_{chunk.chunk_id}" for chunk in chunks]
        texts = [chunk.text for chunk in chunks]

        # Filter metadatas to remove lists/dicts
        metadatas = []
        for chunk in chunks:
            chunk_dict = chunk.to_dict()
            # Remove fields that are lists or dicts (ChromaDB only accepts primitives)
            filtered_dict = {
                k: v for k, v in chunk_dict.items()
                if not isinstance(v, (list, dict)) and v is not None
            }
            metadatas.append(filtered_dict)

        # Generate embeddings
        from mchp_mcp_core.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = self.embedder.embed(texts, show_progress=show_progress)

        # Convert to list format
        if hasattr(embeddings, 'tolist'):
            embeddings_list = embeddings.tolist()
        else:
            embeddings_list = [list(e) for e in embeddings]

        # Add to ChromaDB in batches
        chunks_added = 0
        for i in range(0, len(chunks), batch_size):
            end_idx = min(i + batch_size, len(chunks))

            self.collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings_list[i:end_idx],
                documents=texts[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )

            chunks_added += (end_idx - i)

        logger.info(f"Added {chunks_added} chunks to ChromaDB")
        return chunks_added, 0

console = Console()


class DocumentEmbedder:
    """Embeds extracted documents and indexes them in ChromaDB.

    Leverages mchp-mcp-core for embeddings and vector storage.
    """

    def __init__(
        self,
        chroma_path: Optional[Path] = None,
        collection_name: str = "fpga_docs"
    ):
        """Initialize embedder and vector store.

        Args:
            chroma_path: Path to ChromaDB storage (default: from settings)
            collection_name: Collection name for documents
        """
        self.chroma_path = chroma_path or settings.chroma_path
        self.collection_name = collection_name

        console.print(f"[cyan]Initializing DocumentEmbedder...[/cyan]")

        # Initialize embedding model
        console.print("  Loading embedding model...")
        self.embedder = EmbeddingModel()
        console.print(f"  [green]✓ Model loaded: {self.embedder.model_name}[/green]")
        console.print(f"  [green]✓ Device: {self.embedder.device}[/green]")
        console.print(f"  [green]✓ Dimension: {self.embedder.dimension}[/green]")

        # Initialize vector store
        console.print(f"  Setting up ChromaDB at {self.chroma_path}...")
        self.vector_store = ChromaDBVectorStore(
            db_path=str(self.chroma_path),
            collection_name=collection_name,
            embedding_model=self.embedder
        )

        if self.vector_store.is_available():
            info = self.vector_store.get_collection_info()
            console.print(f"  [green]✓ ChromaDB initialized ({info['points_count']} existing docs)[/green]")
        else:
            console.print("  [red]✗ ChromaDB not available - install with: pip install chromadb[/red]")

    def _chunk_text_simple(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Simple fixed-size chunking with overlap.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                # Look for last sentence boundary in chunk
                for sep in ['. ', '.\n', '! ', '?\n']:
                    last_sep = chunk.rfind(sep)
                    if last_sep > chunk_size // 2:  # At least halfway through
                        end = start + last_sep + len(sep)
                        chunk = text[start:end]
                        break

            chunks.append(chunk.strip())
            start = end - overlap if end < len(text) else end

        return chunks

    def _create_chunks_from_pages(
        self,
        doc_id: str,
        version: str,
        pages: List[tuple[int, str]],  # (page_num, text)
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[DocumentChunk]:
        """Create DocumentChunks from page text using fixed-size chunking.

        Args:
            doc_id: Document identifier
            version: Document version
            pages: List of (page_number, text) tuples
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of DocumentChunk objects
        """
        chunks = []

        for page_num, page_text in pages:
            if not page_text.strip():
                continue

            # Chunk the page text
            text_chunks = self._chunk_text_simple(page_text, chunk_size, overlap)

            for chunk_id, chunk_text in enumerate(text_chunks):
                # Compute hash for deduplication
                content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()

                # Create DocumentChunk
                chunk = DocumentChunk(
                    doc_id=doc_id,
                    title=doc_id,  # Use doc_id as title
                    source_path=doc_id,
                    updated_at=datetime.now().isoformat(),
                    slide_or_page=page_num,
                    chunk_id=chunk_id,
                    text=chunk_text,
                    sha256=content_hash,
                    version=version,
                    product_family="PolarFire"  # Default for now
                )
                chunks.append(chunk)

        return chunks

    def index_document(
        self,
        doc_id: str,
        version: str,
        content_dir: Path,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> int:
        """Index a single document from its content directory.

        Args:
            doc_id: Document identifier
            version: Document version
            content_dir: Path to content/{doc_id}/{version}
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            Number of chunks indexed
        """
        text_dir = content_dir / "text"
        if not text_dir.exists():
            console.print(f"[yellow]  Warning: No text directory found at {text_dir}[/yellow]")
            return 0

        # Read all page text files
        pages = []
        for text_file in sorted(text_dir.glob("page_*.txt")):
            # Extract page number from filename
            page_num = int(text_file.stem.split("_")[1])
            text = text_file.read_text(encoding="utf-8", errors="ignore")
            pages.append((page_num, text))

        if not pages:
            console.print(f"[yellow]  Warning: No pages found in {text_dir}[/yellow]")
            return 0

        console.print(f"[cyan]  Creating chunks from {len(pages)} pages...[/cyan]")
        chunks = self._create_chunks_from_pages(doc_id, version, pages, chunk_size, overlap)
        console.print(f"  [green]✓ Created {len(chunks)} chunks[/green]")

        if not self.vector_store.is_available():
            console.print("  [red]✗ Cannot index - ChromaDB not available[/red]")
            return 0

        # Add to vector store
        console.print(f"[cyan]  Indexing chunks...[/cyan]")
        chunks_added, duplicates = self.vector_store.add_documents(chunks)
        console.print(f"  [green]✓ Indexed {chunks_added} chunks ({duplicates} duplicates skipped)[/green]")

        return chunks_added

    def index_all_documents(
        self,
        content_root: Optional[Path] = None,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> int:
        """Index all documents in the content directory.

        Args:
            content_root: Root content directory (default: from settings)
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            Total chunks indexed
        """
        content_root = content_root or settings.content_dir
        if not content_root.exists():
            console.print(f"[red]Content directory not found: {content_root}[/red]")
            return 0

        # Find all document version directories
        doc_dirs = []
        for doc_id_dir in content_root.iterdir():
            if not doc_id_dir.is_dir():
                continue

            for version_dir in doc_id_dir.iterdir():
                if not version_dir.is_dir():
                    continue

                # Check if this version has a text directory
                if (version_dir / "text").exists():
                    doc_dirs.append((doc_id_dir.name, version_dir.name, version_dir))

        if not doc_dirs:
            console.print("[yellow]No documents found to index[/yellow]")
            return 0

        console.print(f"\n[bold cyan]Indexing {len(doc_dirs)} documents...[/bold cyan]\n")

        total_chunks = 0
        for doc_id, version, content_dir in track(doc_dirs, description="Indexing documents"):
            console.print(f"\n[bold]{doc_id} ({version})[/bold]")
            chunks = self.index_document(doc_id, version, content_dir, chunk_size, overlap)
            total_chunks += chunks

        console.print(f"\n[bold green]✓ Indexed {total_chunks} total chunks from {len(doc_dirs)} documents[/bold green]")

        return total_chunks
