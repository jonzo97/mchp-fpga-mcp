#!/usr/bin/env python
"""CLI entrypoint for staging and enqueuing documents."""
from __future__ import annotations

import asyncio
import click

from fpga_rag.ingestion import IngestionOrchestrator


@click.command()
@click.option("--directory", "directory", type=click.Path(path_type=str, exists=True), default=None,
              help="Directory containing PDFs to ingest (defaults to configured incoming dir).")
def main(directory: str | None) -> None:
    orchestrator = IngestionOrchestrator()
    jobs = list(orchestrator.stage_from_directory()) if directory is None else list(
        orchestrator.stage_from_directory(directory)
    )
    click.echo(f"Staged {len(jobs)} document(s)")
    asyncio.run(orchestrator.enqueue_jobs(jobs))


if __name__ == "__main__":
    main()
