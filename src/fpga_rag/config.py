"""Configuration models and helpers for the FPGA RAG system."""
from __future__ import annotations

from pathlib import Path

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Runtime configuration for ingestion and server components."""

    # Directory paths
    base_dir: Path = Field(default=Path(__file__).resolve().parents[2])
    incoming_dir: Path = Field(default_factory=lambda: Path.cwd() / "incoming")
    content_dir: Path = Field(default_factory=lambda: Path.cwd() / "content")
    manifest_db_path: Path = Field(default_factory=lambda: Path.cwd() / "manifest.db")
    chroma_path: Path = Field(default_factory=lambda: Path.cwd() / "chroma")
    duckdb_path: Path = Field(default_factory=lambda: Path.cwd() / "duckdb" / "tables.duckdb")

    # Backend services
    redis_url: str = Field(default="redis://localhost:6379/0")
    orchestra_backend: str = Field(default="sqlite")

    # MCP Server settings
    mcp_collection_name: str = Field(default="fpga_docs")
    mcp_default_top_k: int = Field(default=5)
    mcp_max_top_k: int = Field(default=20)
    mcp_max_snippet_length: int = Field(default=500)
    mcp_max_tables_per_result: int = Field(default=3)
    mcp_log_level: str = Field(default="INFO")

    # Embedding settings
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
    max_tokens_per_chunk: int = Field(default=1500)
    overlap_tokens: int = Field(default=150)

    class Config:
        env_file = ".env"
        env_prefix = "FPGA_RAG_"
        case_sensitive = False


settings = Settings()
