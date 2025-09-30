"""Manifest data models for document ingestion."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select


class ManifestStatus(str, Enum):
    """Lifecycle of a manifest entry."""

    STAGED = "staged"
    QUEUED = "queued"
    EXTRACTING = "extracting"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class ManifestEntry(SQLModel, table=True):
    """SQLModel representation of a manifest row."""

    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: str = Field(index=True)
    version: str = Field(index=True)
    source_url: Optional[str] = Field(default=None)
    checksum: str = Field(unique=True, index=True)
    size_bytes: int
    page_count: Optional[int] = Field(default=None)
    status: ManifestStatus = Field(default=ManifestStatus.STAGED)
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    notes: Optional[str] = Field(default=None)


@dataclass
class DocumentManifest:
    """Serialisable manifest representation for transport and business logic."""

    doc_id: str
    version: str
    checksum: str
    size_bytes: int
    status: ManifestStatus
    source_url: Optional[str] = None
    page_count: Optional[int] = None
    notes: Optional[str] = None


class ManifestRepository:
    """Database-backed manifest persistence helper."""

    def __init__(self, db_path: Path) -> None:
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        SQLModel.metadata.create_all(self.engine)

    def upsert(self, entry: DocumentManifest) -> ManifestEntry:
        with Session(self.engine) as session:
            stmt = select(ManifestEntry).where(ManifestEntry.checksum == entry.checksum)
            existing = session.exec(stmt).first()
            now = dt.datetime.now(dt.timezone.utc)
            if existing:
                existing.doc_id = entry.doc_id
                existing.version = entry.version
                existing.status = entry.status
                existing.source_url = entry.source_url
                existing.size_bytes = entry.size_bytes
                existing.page_count = entry.page_count
                existing.notes = entry.notes
                existing.updated_at = now
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing

            manifest_entry = ManifestEntry(
                doc_id=entry.doc_id,
                version=entry.version,
                checksum=entry.checksum,
                size_bytes=entry.size_bytes,
                status=entry.status,
                source_url=entry.source_url,
                page_count=entry.page_count,
                notes=entry.notes,
                created_at=now,
                updated_at=now,
            )
            session.add(manifest_entry)
            session.commit()
            session.refresh(manifest_entry)
            return manifest_entry

    def list_by_status(self, status: ManifestStatus) -> Iterable[ManifestEntry]:
        with Session(self.engine) as session:
            stmt = select(ManifestEntry).where(ManifestEntry.status == status)
            return session.exec(stmt).all()

    def update_status(self, checksum: str, status: ManifestStatus, notes: Optional[str] = None) -> None:
        with Session(self.engine) as session:
            stmt = select(ManifestEntry).where(ManifestEntry.checksum == checksum)
            entry = session.exec(stmt).first()
            if not entry:
                raise ValueError(f"Manifest entry with checksum {checksum} not found")
            entry.status = status
            entry.updated_at = dt.datetime.now(dt.timezone.utc)
            if notes:
                entry.notes = notes
            session.add(entry)
            session.commit()

