#!/usr/bin/env python3
"""ChromaDB adapter supporting both persistent and HTTP client modes.

This adapter provides a unified interface for ChromaDB operations that works with:
1. Persistent ChromaDB (file-based) - PRIMARY for local development
2. HTTP ChromaDB (client-server) - SECONDARY for production deployment
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

logger = logging.getLogger(__name__)


class ChromaAdapter:
    """Wrapper for ChromaDB vector database operations.

    Supports both persistent (file-based) and HTTP (client-server) modes.
    Automatically falls back to persistent mode if HTTP unavailable.
    """

    def __init__(
        self,
        mode: str = "persistent",
        db_path: Optional[Path | str] = None,
        host: str = "localhost",
        port: int = 8000,
        collection_name: str = "fpga_docs",
    ):
        """Initialize ChromaDB client and collection.

        Args:
            mode: "persistent" (file-based) or "http" (client-server)
            db_path: Path to persistent DB directory (for persistent mode)
            host: ChromaDB server host (for HTTP mode)
            port: ChromaDB server port (for HTTP mode)
            collection_name: Name of the collection to use
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB not available. Install with: pip install chromadb"
            )

        self.mode = mode
        self.db_path = Path(db_path) if db_path else None
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.client = None
        self.collection = None

        # Initialize client based on mode
        if mode == "persistent":
            self._init_persistent()
        elif mode == "http":
            self._init_http()
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'persistent' or 'http'.")

    def _init_persistent(self):
        """Initialize persistent (file-based) ChromaDB client."""
        if not self.db_path:
            raise ValueError("db_path required for persistent mode")

        try:
            self.db_path.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(self.db_path))
            self.collection = self._get_or_create_collection()
            logger.info(f"✅ Persistent ChromaDB initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize persistent ChromaDB: {e}")
            raise

    def _init_http(self):
        """Initialize HTTP ChromaDB client."""
        try:
            self.client = chromadb.HttpClient(host=self.host, port=self.port)

            # Test connection
            if not self.test_connection():
                raise ConnectionError(f"Cannot connect to ChromaDB at {self.host}:{self.port}")

            self.collection = self._get_or_create_collection()
            logger.info(f"✅ HTTP ChromaDB connected at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to HTTP ChromaDB: {e}")
            raise

    def _get_or_create_collection(self):
        """Get existing collection or create new one.

        Returns:
            ChromaDB collection object
        """
        try:
            # Try to get existing collection
            collection = self.client.get_collection(name=self.collection_name)
            count = collection.count()
            logger.info(f"✅ Using existing collection '{self.collection_name}' ({count} docs)")
            return collection
        except Exception:
            # Create new collection if it doesn't exist
            collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "FPGA documentation embeddings"}
            )
            logger.info(f"✅ Created new collection: {self.collection_name}")
            return collection

    def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: List[str],
        batch_size: int = 100,
    ) -> int:
        """Add documents with embeddings to collection in batches.

        Args:
            ids: Unique document IDs
            embeddings: Document embedding vectors
            metadatas: Document metadata dicts
            documents: Document text content
            batch_size: Number of documents per batch

        Returns:
            Number of documents added
        """
        if not all([ids, embeddings, metadatas, documents]):
            raise ValueError("All parameters (ids, embeddings, metadatas, documents) required")

        if not (len(ids) == len(embeddings) == len(metadatas) == len(documents)):
            raise ValueError("All input lists must have same length")

        total_added = 0
        total = len(ids)

        # Process in batches to avoid memory issues
        for i in range(0, total, batch_size):
            end_idx = min(i + batch_size, total)

            batch_ids = ids[i:end_idx]
            batch_embeddings = embeddings[i:end_idx]
            batch_metadatas = metadatas[i:end_idx]
            batch_documents = documents[i:end_idx]

            try:
                self.collection.add(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    metadatas=batch_metadatas,
                    documents=batch_documents,
                )
                total_added += len(batch_ids)
                logger.debug(f"Added batch {i//batch_size + 1}: {total_added}/{total} docs")
            except Exception as e:
                logger.error(f"Failed to add batch {i//batch_size + 1}: {e}")
                # Continue with next batch rather than failing completely
                continue

        logger.info(f"✅ Added {total_added}/{total} documents to collection")
        return total_added

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Query collection with embedding vector.

        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Optional metadata filter (e.g., {"doc_id": "PolarFire_Datasheet"})
            include: Fields to include in results (default: all)

        Returns:
            Query results with ids, distances, metadatas, documents
        """
        if not query_embedding:
            raise ValueError("query_embedding cannot be empty")

        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": include or ["metadatas", "documents", "distances"],
        }

        if where:
            query_params["where"] = where

        try:
            results = self.collection.query(**query_params)

            # Flatten single-query results for convenience
            return {
                "ids": results["ids"][0] if results.get("ids") else [],
                "distances": results["distances"][0] if results.get("distances") else [],
                "metadatas": results["metadatas"][0] if results.get("metadatas") else [],
                "documents": results["documents"][0] if results.get("documents") else [],
            }
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {"ids": [], "distances": [], "metadatas": [], "documents": []}

    def count(self) -> int:
        """Get total number of documents in collection.

        Returns:
            Document count, or 0 if error
        """
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Failed to get count: {e}")
            return 0

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection metadata and statistics.

        Returns:
            Dict with collection info (name, count, metadata)
        """
        try:
            count = self.count()
            metadata = self.collection.metadata

            return {
                "name": self.collection_name,
                "count": count,
                "metadata": metadata,
                "mode": self.mode,
                "path": str(self.db_path) if self.db_path else f"{self.host}:{self.port}",
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}

    def delete_collection(self) -> bool:
        """Delete the entire collection (use with caution!).

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.warning(f"🗑️  Deleted collection: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False

    def test_connection(self) -> bool:
        """Test connection to ChromaDB.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.mode == "http":
                # HTTP mode: use heartbeat
                self.client.heartbeat()
            else:
                # Persistent mode: try to list collections
                self.client.list_collections()
            return True
        except Exception as e:
            logger.debug(f"Connection test failed: {e}")
            return False

    def is_available(self) -> bool:
        """Check if ChromaDB is available and working.

        Returns:
            True if available, False otherwise
        """
        try:
            return self.collection is not None and self.test_connection()
        except Exception:
            return False


def get_chroma_adapter(
    mode: str = "persistent",
    db_path: Optional[Path | str] = None,
    host: str = "localhost",
    port: int = 8000,
    collection_name: str = "fpga_docs",
    fallback_to_persistent: bool = True,
) -> Optional[ChromaAdapter]:
    """Get ChromaDB adapter with automatic fallback.

    Tries HTTP mode first (if specified), then falls back to persistent mode.

    Args:
        mode: "persistent" or "http"
        db_path: Path for persistent DB
        host: HTTP server host
        port: HTTP server port
        collection_name: Collection name
        fallback_to_persistent: If True, fallback from HTTP to persistent on failure

    Returns:
        ChromaAdapter instance if available, None otherwise
    """
    if not CHROMADB_AVAILABLE:
        logger.error("ChromaDB not installed. Install with: pip install chromadb")
        return None

    # Try requested mode first
    try:
        adapter = ChromaAdapter(
            mode=mode,
            db_path=db_path,
            host=host,
            port=port,
            collection_name=collection_name,
        )
        if adapter.is_available():
            logger.info(f"✅ ChromaDB adapter initialized in {mode} mode")
            return adapter
    except Exception as e:
        logger.warning(f"Failed to initialize ChromaDB in {mode} mode: {e}")

    # Fallback to persistent if HTTP failed
    if mode == "http" and fallback_to_persistent and db_path:
        logger.info("Attempting fallback to persistent mode...")
        try:
            adapter = ChromaAdapter(
                mode="persistent",
                db_path=db_path,
                collection_name=collection_name,
            )
            if adapter.is_available():
                logger.info("✅ Fallback to persistent ChromaDB successful")
                return adapter
        except Exception as e:
            logger.error(f"Fallback to persistent mode also failed: {e}")

    logger.error("❌ ChromaDB not available in any mode")
    return None
