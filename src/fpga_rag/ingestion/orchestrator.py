"""Ingestion orchestrator scaffold."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from rich.console import Console
from rich.table import Table

from fpga_rag.config import settings
from fpga_rag.ingestion.manifest import DocumentManifest, ManifestRepository, ManifestStatus
from fpga_rag.utils.hashing import compute_checksum
from fpga_rag.utils.pdf import get_pdf_metadata


console = Console()


@dataclass
class IngestionJob:
    """Simple ingestion job representation."""

    path: Path
    manifest: DocumentManifest


class IngestionOrchestrator:
    """Coordinates staging and queueing of document ingestion jobs."""

    def __init__(self, repo: Optional[ManifestRepository] = None) -> None:
        self.repo = repo or ManifestRepository(settings.manifest_db_path)

    def stage_from_directory(self, directory: Path | None = None) -> Iterable[IngestionJob]:
        """Scan a directory for PDFs and register manifest entries."""

        directory = directory or settings.incoming_dir
        jobs: list[IngestionJob] = []
        for pdf_path in sorted(directory.glob("*.pdf")):
            metadata = get_pdf_metadata(pdf_path)
            checksum = compute_checksum(pdf_path)
            manifest = DocumentManifest(
                doc_id=metadata.doc_id,
                version=metadata.version,
                checksum=checksum,
                size_bytes=metadata.size_bytes,
                status=ManifestStatus.STAGED,
                source_url=metadata.source_url,
                page_count=metadata.page_count,
                notes=metadata.notes,
            )
            self.repo.upsert(manifest)
            jobs.append(IngestionJob(path=pdf_path, manifest=manifest))
        return jobs

    async def enqueue_jobs(self, jobs: Iterable[IngestionJob]) -> None:
        """Placeholder async queue submission."""

        await asyncio.sleep(0)  # placeholder for queue client
        table = Table(title="Queued Ingestion Jobs")
        table.add_column("Doc ID")
        table.add_column("Version")
        table.add_column("Checksum")
        table.add_column("Pages")
        for job in jobs:
            table.add_row(
                job.manifest.doc_id,
                job.manifest.version,
                job.manifest.checksum[:8],
                str(job.manifest.page_count or "?")
            )
        console.print(table)

