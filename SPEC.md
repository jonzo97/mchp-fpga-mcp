# FPGA Document RAG System Specification

## Objectives & Scope
Build a local-first retrieval-augmented generation (RAG) system that ingests Microchip PolarFire PDFs (and future FPGA collateral), preserves layout-aware text, tables, and figures, and serves multimodal retrieval and rule-extraction tools through an MCP-compliant server. The pipeline must scale to hundreds of long documents, support offline operation inside WSL, and leave room for GPU acceleration when available.

## Key Constraints & Assumptions
- Primary runtime inside WSL2 Ubuntu; Windows hosts only editors/viewers. GPU passthrough is optional but preferred for OCR/vision models.
- Inputs arrive as vendor PDFs, possibly large (1000+ pages) with scanned sections. Supplemental assets (tables, figures, scripts) may follow.
- No external SaaS dependencies; all services (Chroma, manifests, object store) run locally via Docker Compose or systemd units.
- Versioning and provenance are critical: every artifact maps back to document id, revision, checksum, and source URL.

## High-Level Architecture
1. **Ingestion Orchestrator** — Watches `incoming/` and manifest queue, validates checksum, and enqueues jobs to a worker pool (Prefect, Celery, or asyncio-based dispatcher).
2. **Document Processing Workers** — Pipeline built around docTR + Layout Parser for layout-aware extraction, supplemented by Unstructured or LlamaParse interfaces when beneficial.
3. **Artifact Store** — Directory hierarchy under `content/` holding normalized text JSON, table CSV/Parquet, cropped figure images, captions, and thumbnails.
4. **Metadata & Manifest DB** — Lightweight relational DB (SQLite → PostgreSQL) storing document metadata, section hierarchy, chunk stats, and processing status.
5. **Vector & Keyword Indexes** — Chroma for modality-specific vector collections; Tantivy/Whoosh (or Vespa-lite) for BM25 keyword search; optional DuckDB sidecar for structured tables.
6. **Retrieval Layer** — Hybrid search and reranking pipeline combining vector, BM25, and deterministic lookups; feeds rule-extraction prompts.
7. **MCP Server** — FastAPI + MCP adapter exposing ingestion, semantic search, visual chunk retrieval, rule extraction, and revision comparison tools.

## Document Ingestion Flow
1. **Staging** — Place files in `incoming/`; a `watchman`-style file watcher or CLI command computes SHA256, size, and extracts PDF metadata.
2. **Manifest Entry** — Persist `(doc_id, version, source_url, checksum, ingest_ts, status)` in `manifest` table; attach optional release notes.
3. **Preflight Checks** — Run `pdfinfo`, sanity-page-count thresholds, and virus scan hook. Reject duplicates via checksum comparison.
4. **Queue & Parallelism** — Push to a durable queue (Redis Stream or SQLite job table) consumed by worker processes; limit concurrency per GPU/CPU availability.
5. **Processing Lifecycle** — Workers advance status states (queued → extracting → indexing → ready). Failures retain logs and partial artifacts for inspection.
6. **Versioning** — New versions live alongside prior ones; use semantic doc ids (`pf_transceiver_ug:VB`). Maintain symlinks for "latest" views.

## Extraction & Enrichment
### Text & Section Hierarchy
- Use docTR for OCR + geometry, feeding Layout Parser for layout segmentation and heading detection.
- Maintain per-block JSON (`page`, `bbox`, `text`, `section_path`, `block_type`, `confidence`). Clean headers/footers via heuristics or ML classifier.
- Chunk text for embeddings by section-aware sliding windows; keep tokens under 1.5k for consistent LLM prompts.

### Tables
- Export each table to both CSV and Parquet with companion schema JSON (`column_types`, `units`, `source_page`).
- For complex layout, run Unstructured's table extraction or LlamaParse's structured output as a fallback, reconciling via schema comparison.
- Store quick-look PNG thumbnails for QA and retrieval previews.

### Figures & Diagrams
- Crop figure regions using Layout Parser bounding boxes. Save as WebP at 300 dpi and run Tesseract or PaddleOCR for embedded text.
- Generate captions via BLIP/LAVIS with FPGA-aware prompt template and store embeddings with CLIP/OpenCLIP.
- Persist relationships: `figure -> referenced_table`, `figure -> section`, `caption -> text_chunk_id` for cross-modal querying.

## Visual Extraction Tooling Plan
| Tool | Strengths | Limitations | Planned Role |
| --- | --- | --- | --- |
| docTR | Fast OCR + geometry, good for full-page text | Table structure limited; needs GPU for best speed | Baseline OCR & token geometry |
| Layout Parser | Flexible layout detection, supports custom detectors | Requires training data for improved accuracy | Segment text/table/figure regions |
| Unstructured | Quick start, good for semi-structured outputs, integrates with chunkers | SaaS features gated; local pipeline CPU-heavy | Fallback parser for tricky tables/structured text |
| LlamaParse | High-fidelity structured extraction, table/figure metadata | Cloud-only today; cost and latency concerns | Evaluate if local open-source alternative unavailable; optional premium tier |
| pdfplumber + heuristics | Lightweight text/table extraction | No OCR, fails on scans | Assist for digital-first PDFs to speed pipeline |

**Evaluation Plan:**
1. Assemble gold set of 15 pages mixing text, tables, schematics, and scanned content.
2. Benchmark docTR+Layout Parser versus Unstructured and LlamaParse on accuracy (cell F1, text BLEU), throughput, and setup cost.
3. Adopt docTR/LP as core; wire in Unstructured through adapters for fallback cases; leave hooks for LlamaParse if cloud access becomes acceptable.
4. Encapsulate each extractor behind a uniform interface so future tools (Nougat, Marker) can slot in without refactoring downstream code.

## Storage & Indexing
- **Manifest DB:** Start with SQLite + SQLModel; plan migration path to Postgres for multi-user concurrency.
- **Artifact Store:** Organized as `content/<doc_id>/<version>/[text|tables|figures]/`. Include checksums and JSON sidecars.
- **Vector DB:** Chroma running via Docker with collections `fpga_text`, `fpga_tables`, `fpga_figures`. Store payloads (section path, page, bbox, asset URI, hash).
- **Keyword Search:** Tantivy-based index refreshed after each ingest; support prefix and boolean queries for part numbers and register names.
- **Structured Tables:** Load table Parquet files into DuckDB for SQL joins and rule checks.

## Retrieval & Reasoning
- Hybrid query service merges BM25 + vector scores via reciprocal rank fusion. Provide filters by `doc_id`, `revision`, `section`, `content_type`.
- Cross-encoder reranker (e.g., `bce-rr-base` or `ms-marco-MiniLM-L-6-v2`) refines top 50 results.
- Rule extraction prompts ingest chunk text, layout metadata, and figure captions, emitting normalized JSON (`rule_id`, `rule_text`, `conditions`, `source_ref`). Store outputs in a `rules` collection with validation schema.
- Offer deterministic table lookups via DuckDB for constraints (timing tables, pin assignments).

## MCP Server & Tooling
- Implement FastAPI app with MCP adapter exposing tools: `ingest_fpga_docs`, `semantic_search`, `get_visual_chunk`, `rule_extractor`, `compare_revisions`, `list_changed`.
- Share embedding and indexing utilities across ingestion and runtime via shared library module.
- Support streaming responses for long-running tasks (ingest). Emit tool notifications when new docs or rules land.
- Authentication optional; for local usage rely on Unix user isolation, but design for API token support later.

## Scalability & Operations
- Containerize services (Chroma, DuckDB server if needed, Redis) via Docker Compose. Keep ingestion workers in separate containers for horizontal scaling.
- Use configurable concurrency limits and rate limiting per modality (text vs vision) to avoid GPU thrash.
- Add Prometheus metrics: ingest latency, chunk counts, embedding queue depth, OCR error rates. Expose health endpoints for orchestrator and MCP server.
- Implement snapshot backups for `manifest.db`, `content/`, and Chroma volumes. Store hashes for periodic integrity checks.
- Provide CLI tooling for bulk re-embedding when models update.

## Next Steps
1. Validate docTR and Layout Parser on a representative sample; record precision/recall for tables and figures.
2. Stand up local Chroma + DuckDB instances and define initial schema migrations.
3. Scaffold ingestion orchestrator (CLI + worker) and stub MCP tools with mocked data.
4. Draft rule-extraction prompt templates and evaluation rubric.
5. Document environment bootstrap (conda/venv, system packages such as poppler, tesseract, torch).
