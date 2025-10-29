"""Storage adapters for FPGA documentation RAG system.

Provides unified interfaces for vector databases and metadata storage.
"""
from .chroma_adapter import ChromaAdapter, get_chroma_adapter

__all__ = ["ChromaAdapter", "get_chroma_adapter"]
