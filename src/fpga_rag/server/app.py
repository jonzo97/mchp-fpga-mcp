"""FastAPI scaffold for the MCP server."""
from __future__ import annotations

from fastapi import FastAPI

from fpga_rag.ingestion import IngestionOrchestrator


def create_app() -> FastAPI:
    """Return a configured FastAPI application."""

    app = FastAPI(title="FPGA RAG MCP Server", version="0.1.0")
    orchestrator = IngestionOrchestrator()

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/tools/ingest")
    async def ingest_documents() -> dict[str, str | int]:
        jobs = list(orchestrator.stage_from_directory())
        await orchestrator.enqueue_jobs(jobs)
        return {"status": "queued", "count": len(jobs)}

    return app


app = create_app()
