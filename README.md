# FPGA Document RAG Stack

Scaffold for a local-first retrieval-augmented generation system focused on Microchip PolarFire FPGA collateral.

## Components
- `incoming/` – staging area for vendor PDFs before ingest.
- `content/` – normalized text, tables, figures, and derived artifacts.
- `src/fpga_rag/` – Python package housing ingestion workers, storage adapters, and MCP server.
- `scripts/` – CLI utilities for ingestion and maintenance.
- `tests/` – pytest-based checks for pipeline units.

## Getting Started

### 1. Install mchp-mcp-core (Development Dependency)

This project depends on `mchp-mcp-core` for PDF extraction, embeddings, and vector storage.

```bash
# Install mchp-mcp-core in editable mode for development
cd ~/mchp-mcp-core
pip install -e .
```

Installing in editable mode (`-e`) means changes to mchp-mcp-core are immediately available without reinstalling.

**Note:** As of 2025-11-14, fpga_mcp uses `mchp-mcp-core` for enhanced PDF extraction including:
- **Multi-strategy table extraction** - 3-way consensus (pdfplumber + Camelot + PyMuPDF)
- **Structure-aware chunking** - Preserves section hierarchy
- **Specification extraction** - Extracts electrical parameters (voltage, current, timing)
- **~2x more content extracted** compared to previous pdftotext-only approach

This migration maintains full backward compatibility with existing ingestion pipeline and ExtractionWorker API.

### 2. Install fpga_mcp

```bash
cd ~/fpga_mcp
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 3. Ingest FPGA PDFs

```bash
# Populate incoming/ with FPGA PDFs
python scripts/ingest.py
```

### 4. Run the MCP Server

```bash
uvicorn fpga_rag.server.app:app --reload
```

Refer to `SPEC.md` for the full system design and roadmap.
