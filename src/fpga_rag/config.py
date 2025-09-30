"""Configuration models and helpers for the FPGA RAG system."""
from __future__ import annotations

from pathlib import Path
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Runtime configuration for ingestion and server components."""

    base_dir: Path = Field(default=Path(__file__).resolve().parents[2])
    incoming_dir: Path = Field(default_factory=lambda: Path.cwd() / "incoming")
    content_dir: Path = Field(default_factory=lambda: Path.cwd() / "content")
    manifest_db_path: Path = Field(default_factory=lambda: Path.cwd() / "manifest.db")
    chroma_path: Path = Field(default_factory=lambda: Path.cwd() / "chroma")
    duckdb_path: Path = Field(default_factory=lambda: Path.cwd() / "duckdb" / "tables.duckdb")
    redis_url: str = Field(default="redis://localhost:6379/0")
    orchestra_backend: str = Field(default="sqlite")

    class Config:
        env_file = ".env"
        env_prefix = "FPGA_RAG_"
        case_sensitive = False


settings = Settings()
