# FPGA Document RAG Stack

Scaffold for a local-first retrieval-augmented generation system focused on Microchip PolarFire FPGA collateral.

## Components
- `incoming/` – staging area for vendor PDFs before ingest.
- `content/` – normalized text, tables, figures, and derived artifacts.
- `src/fpga_rag/` – Python package housing ingestion workers, storage adapters, and MCP server.
- `scripts/` – CLI utilities for ingestion and maintenance.
- `tests/` – pytest-based checks for pipeline units.

## Getting Started
1. Create a Python 3.10+ virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```
2. Populate `incoming/` with FPGA PDFs.
3. Stage and enqueue jobs:
   ```bash
   python scripts/ingest.py
   ```
4. Run the FastAPI MCP stub:
   ```bash
   uvicorn fpga_rag.server.app:app --reload
   ```

Refer to `SPEC.md` for the full system design and roadmap.
