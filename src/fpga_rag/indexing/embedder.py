"""Document embedding and indexing using mchp-mcp-core."""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Add mchp-mcp-core to path
MCHP_CORE_PATH = Path.home() / "mchp-mcp-core"
if str(MCHP_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(MCHP_CORE_PATH))

from mchp_mcp_core.embeddings.sentence_transformers import EmbeddingModel
from mchp_mcp_core.extractors.chunking import perform_intelligent_chunking
from mchp_mcp_core.models.common import ExtractedChunk
from mchp_mcp_core.storage.chromadb import ChromaDBVectorStore as _ChromaDBVectorStore
from mchp_mcp_core.storage.schemas import DocumentChunk
from rich.console import Console
from rich.progress import track

from fpga_rag.config import settings
from fpga_rag.utils.text_cleaning import clean_document_pages
from fpga_rag.utils.token_counter import count_tokens, estimate_tokens


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

    def _create_page_chunks(
        self,
        doc_id: str,
        version: str,
        pages: List[Tuple[int, str]]  # (page_num, text)
    ) -> List[ExtractedChunk]:
        """Create ExtractedChunk objects from page text for semantic chunking.

        Args:
            doc_id: Document identifier
            version: Document version
            pages: List of (page_number, text) tuples

        Returns:
            List of ExtractedChunk objects (one per page initially)
        """
        chunks = []

        for page_num, page_text in pages:
            if not page_text.strip():
                continue

            # Detect section hierarchy from page text (simple heuristic)
            section_hierarchy = self._extract_section_hierarchy(page_text)

            # Create ExtractedChunk for this page
            chunk = ExtractedChunk(
                chunk_id=f"{doc_id}_p{page_num}",
                content=page_text,
                page_start=page_num,
                page_end=page_num,
                chunk_type="text",
                section_hierarchy=section_hierarchy,
                metadata={
                    "doc_id": doc_id,
                    "version": version,
                    "extraction_method": "pdftotext"
                }
            )
            chunks.append(chunk)

        return chunks

    def _extract_section_hierarchy(self, text: str) -> str:
        """Extract section hierarchy from text (if present).

        Args:
            text: Page text

        Returns:
            Section hierarchy string (e.g., "1.2.3 Section Title") or empty string
        """
        import re

        # Look for numbered sections in first few lines
        lines = text.split('\n')[:10]
        for line in lines:
            line_clean = line.strip()
            # Match patterns like "1.2.3 Section Title"
            match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)$', line_clean)
            if match and len(line_clean) < 80:
                return line_clean
        return ""

    def _split_chunk_by_tokens(
        self,
        chunk: ExtractedChunk,
        max_tokens: int,
        overlap_tokens: int
    ) -> List[ExtractedChunk]:
        """Split a chunk that exceeds max_tokens at sentence boundaries.

        Args:
            chunk: Chunk to split
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Overlap between split chunks

        Returns:
            List of split chunks (or original if within limit)
        """
        from fpga_rag.utils.token_counter import chunk_by_tokens

        # Check if chunk needs splitting
        current_tokens = count_tokens(chunk.content)
        if current_tokens <= max_tokens:
            return [chunk]

        # Split using token-aware chunker
        split_texts = chunk_by_tokens(
            chunk.content,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens
        )

        # Create new chunks preserving metadata
        split_chunks = []
        for i, text in enumerate(split_texts):
            new_chunk = ExtractedChunk(
                chunk_id=f"{chunk.chunk_id}_split{i}",
                content=text,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                chunk_type=chunk.chunk_type,
                section_hierarchy=chunk.section_hierarchy,
                metadata={
                    **chunk.metadata,
                    "split_from": chunk.chunk_id,
                    "split_index": i
                }
            )
            split_chunks.append(new_chunk)

        return split_chunks

    def _enforce_token_limits(
        self,
        chunks: List[ExtractedChunk],
        max_tokens: int,
        overlap_tokens: int
    ) -> List[ExtractedChunk]:
        """Enforce token limits by splitting oversized chunks.

        Args:
            chunks: Chunks from semantic chunking
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Overlap for split chunks

        Returns:
            List of chunks with enforced token limits
        """
        enforced_chunks = []
        oversized_count = 0

        for chunk in chunks:
            token_count = count_tokens(chunk.content)

            if token_count > max_tokens:
                oversized_count += 1
                # Split this chunk
                split_chunks = self._split_chunk_by_tokens(chunk, max_tokens, overlap_tokens)
                enforced_chunks.extend(split_chunks)
            else:
                enforced_chunks.append(chunk)

        if oversized_count > 0:
            console.print(f"  [dim]Split {oversized_count} oversized chunks → {len(enforced_chunks)} total[/dim]")

        return enforced_chunks

    def _create_chunks_from_pages(
        self,
        doc_id: str,
        version: str,
        pages: List[Tuple[int, str]],  # (page_num, text)
        max_tokens: int = 1500,
        overlap_tokens: int = 150,
        use_semantic: bool = True
    ) -> List[DocumentChunk]:
        """Create DocumentChunks using semantic chunking and token-based limits.

        Args:
            doc_id: Document identifier
            version: Document version
            pages: List of (page_number, text) tuples
            max_tokens: Target chunk size in tokens (not characters!)
            overlap_tokens: Overlap between chunks in tokens
            use_semantic: Use semantic (section-aware) chunking

        Returns:
            List of DocumentChunk objects
        """
        console.print(f"  [dim]Token-based semantic chunking (max {max_tokens} tokens)...[/dim]")

        # Step 1: Clean pages (remove headers/footers)
        cleaned_pages = clean_document_pages(pages, aggressive=False, detect_repeats=True)
        console.print(f"  [dim]Cleaned {len(pages)} pages → {len(cleaned_pages)} non-empty[/dim]")

        # Step 2: Create ExtractedChunk objects for semantic chunking
        extracted_chunks = self._create_page_chunks(doc_id, version, cleaned_pages)

        # Step 3: Apply intelligent semantic chunking from mchp-mcp-core
        # Convert token limits to approximate character limits (1 token ≈ 4 chars for English text)
        # This is just a rough target; token limits will be enforced in Step 3.5
        chunk_size_chars = int(max_tokens * 4)
        overlap_chars = int(overlap_tokens * 4)

        if use_semantic:
            final_chunks = perform_intelligent_chunking(
                extracted_chunks,
                chunk_size=chunk_size_chars,
                overlap=overlap_chars,
                chunking_strategy="semantic",
                min_chunk_size=chunk_size_chars // 3,
                max_chunk_size=chunk_size_chars * 2
            )
        else:
            final_chunks = perform_intelligent_chunking(
                extracted_chunks,
                chunk_size=chunk_size_chars,
                overlap=overlap_chars,
                chunking_strategy="fixed"
            )

        console.print(f"  [dim]Semantic chunking: {len(extracted_chunks)} pages → {len(final_chunks)} chunks[/dim]")

        # Step 3.5: Enforce token limits by splitting oversized chunks
        final_chunks = self._enforce_token_limits(final_chunks, max_tokens, overlap_tokens)

        # Step 4: Convert ExtractedChunk to DocumentChunk for ChromaDB
        document_chunks = []
        for idx, chunk in enumerate(final_chunks):
            # Compute hash for deduplication
            content_hash = hashlib.sha256(chunk.content.encode()).hexdigest()

            # Count actual tokens
            token_count = count_tokens(chunk.content)

            document_chunk = DocumentChunk(
                doc_id=doc_id,
                title=doc_id,
                source_path=doc_id,
                updated_at=datetime.now().isoformat(),
                slide_or_page=chunk.page_start,
                chunk_id=idx,
                text=chunk.content,
                sha256=content_hash,
                version=version,
                product_family="PolarFire",  # Default for now
                section=chunk.section_hierarchy,  # Preserve section info!
                metadata={
                    **chunk.metadata,
                    "page_end": chunk.page_end,
                    "token_count": token_count,
                    "chunking_strategy": chunk.metadata.get("chunking_strategy", "semantic")
                }
            )
            document_chunks.append(document_chunk)

        return document_chunks

    def index_document(
        self,
        doc_id: str,
        version: str,
        content_dir: Path,
        max_tokens: int = 1500,
        overlap_tokens: int = 150,
        use_semantic: bool = True
    ) -> int:
        """Index a single document from its content directory.

        Args:
            doc_id: Document identifier
            version: Document version
            content_dir: Path to content/{doc_id}/{version}
            max_tokens: Maximum tokens per chunk (default: 1500)
            overlap_tokens: Overlap between chunks in tokens (default: 150)
            use_semantic: Use semantic (section-aware) chunking

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

        console.print(f"[cyan]  Processing {len(pages)} pages...[/cyan]")
        chunks = self._create_chunks_from_pages(
            doc_id, version, pages,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            use_semantic=use_semantic
        )
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
        max_tokens: int = 1500,
        overlap_tokens: int = 150,
        use_semantic: bool = True
    ) -> int:
        """Index all documents in the content directory.

        Args:
            content_root: Root content directory (default: from settings)
            max_tokens: Maximum tokens per chunk (default: 1500)
            overlap_tokens: Overlap between chunks in tokens (default: 150)
            use_semantic: Use semantic (section-aware) chunking

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

        console.print(f"\n[bold cyan]Indexing {len(doc_dirs)} documents with semantic chunking (max {max_tokens} tokens)...[/bold cyan]\n")

        total_chunks = 0
        for doc_id, version, content_dir in track(doc_dirs, description="Indexing documents"):
            console.print(f"\n[bold]{doc_id} ({version})[/bold]")
            chunks = self.index_document(
                doc_id, version, content_dir,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
                use_semantic=use_semantic
            )
            total_chunks += chunks

        console.print(f"\n[bold green]✓ Indexed {total_chunks} total chunks from {len(doc_dirs)} documents[/bold green]")

        return total_chunks
