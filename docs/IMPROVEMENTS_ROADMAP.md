# FPGA MCP Server Improvements Roadmap

**Last Updated:** 2025-10-28
**Status:** Phase 1 In Progress
**Goal:** Production-ready MCP server with tcl_monster integration

## Overview

This roadmap tracks improvements to merge production-ready patterns from Windows repo (`/mnt/c/fpga_mcp`) into local repo (`~/fpga_mcp`), implement quality improvements, and optimize for dual-mode support (Claude Code direct import + Claude Desktop MCP server).

---

## Phase 1: Foundation & Production Patterns (3-4 hours)

### Objectives
- Port production-ready MCP server from Windows repo
- Implement critical quality improvements
- Establish solid testing foundation
- Support dual-mode usage (direct import + MCP server)

### Tasks

#### 1.1 Documentation (COMPLETED)
- ✅ **Update `.claude/CLAUDE.md`** for dual-mode support
  - Changed from "NOT for Claude Desktop" to "Supports both modes"
  - Added MCP server usage examples
  - Updated document count (7 → 27 PDFs)
  - Added tcl_monster integration examples
  - **Status:** COMPLETE (2025-10-28)

- ✅ **Create `docs/IMPROVEMENTS_ROADMAP.md`**
  - This file!
  - **Status:** COMPLETE (2025-10-28)

#### 1.2 Port Production ChromaDB Adapter (30 min)
- ⏳ **Port `/mnt/c/fpga_mcp/tools/chroma_adapter.py`**
  - **Target:** `~/fpga_mcp/src/fpga_rag/storage/chroma_adapter.py`
  - **Features to port:**
    - Connection testing and error handling
    - Batch operations with progress tracking
    - Graceful degradation patterns
    - Automatic fallback mechanism
  - **Status:** PENDING

#### 1.3 Port Production MCP Server (2 hours)
- ⏳ **Port `/mnt/c/fpga_mcp/tools/polarfire_mcp_server.py`**
  - **Target:** `~/fpga_mcp/src/fpga_rag/mcp_server/server.py`
  - **Replace:** Current basic stub (150 lines) with production version (499 lines)
  - **Features to port:**
    - Rich content formatting (text + base64 images + CSV→Markdown tables)
    - `polarfire_search` tool with smart resource limiting
    - `polarfire_browse_diagrams` tool
    - First 3 diagrams as base64, rest as file URIs
    - Comprehensive error handling
  - **Status:** PENDING

#### 1.4 Critical Quality Improvements (1.5 hours)

- ⏳ **Dynamic Document Catalog (20 min)**
  - Replace hardcoded 7-document list at `server.py:154-161`
  - Query ChromaDB metadata dynamically
  - Auto-update as new docs indexed (now 27 PDFs)
  - **File:** `src/fpga_rag/mcp_server/server.py`
  - **Status:** PENDING

- ⏳ **Error Handling & Validation (30 min)**
  - Add Pydantic models for request validation
  - Implement retry logic with tenacity
  - Comprehensive try/except with user-friendly errors
  - Log all errors with context (tool name, query, stack trace)
  - **Files:** `src/fpga_rag/mcp_server/server.py`
  - **Status:** PENDING

- ⏳ **Configuration Unification (15 min)**
  - Move all hardcoded paths to `config.py`
  - Add MCP-specific settings (collection_name, default_top_k, max_top_k)
  - Support `.env` file for deployment
  - **File:** `src/fpga_rag/config.py`
  - **Status:** PENDING

- ⏳ **Structured Logging (15 min)**
  - Add logging to all tool calls
  - Log: tool name, query, duration, result count
  - Add health check that tests ChromaDB availability
  - **File:** `src/fpga_rag/mcp_server/server.py`
  - **Status:** PENDING

- ⏳ **Testing Foundation (30 min)**
  - Create `tests/test_mcp_server.py`
  - Test search with sample queries
  - Test error handling (empty results, malformed queries)
  - Test ChromaDB unavailable scenario
  - Mock embeddings for speed
  - **File:** `tests/test_mcp_server.py`
  - **Status:** PENDING

### Phase 1 Success Criteria
- ✅ MCP server returns rich content (text + images + tables)
- ✅ Dynamic document catalog shows all 27 PDFs
- ✅ All errors have user-friendly messages
- ✅ Basic test suite passes
- ✅ Can be used both via direct import AND as MCP server
- ✅ Documentation reflects dual-mode support

### Phase 1 Deliverables
1. ✅ Updated `.claude/CLAUDE.md`
2. ✅ This roadmap document
3. ⏳ Production MCP server ported
4. ⏳ ChromaDB adapter ported
5. ⏳ Dynamic document catalog
6. ⏳ Error handling & validation
7. ⏳ Unified configuration
8. ⏳ Structured logging
9. ⏳ Test suite foundation

---

## Phase 2: tcl_monster Integration (3-4 hours)

### Objectives
- Add specialized tools for Libero TCL automation
- Support tcl_monster workflows (DDR4, PCIe, CCC, UART, GPIO)
- Enable error resolution and parameter validation
- Document integration patterns

### Tasks

#### 2.1 tcl_monster-Specific Tools (2 hours)

- ⏸️ **Tool: `query_ip_parameters`**
  - **Purpose:** Query IP core parameters for TCL generation
  - **Examples:**
    - "What are valid DDR4 speeds for PF_DDR4?"
    - "What PLL multipliers support 50MHz output from 100MHz input?"
    - "What are the valid UART baud rates for CoreUARTapb?"
  - **Returns:** Parameter tables, valid ranges, configuration examples
  - **Status:** NOT STARTED

- ⏸️ **Tool: `explain_error`**
  - **Purpose:** Parse Libero error logs and search docs for solutions
  - **Examples:**
    - "Critical Warning: Clock domain CDC violation"
    - "Error: Insufficient PLL resources"
    - "Timing constraint not met: setup violation"
  - **Returns:** Potential fixes with document citations
  - **Status:** NOT STARTED

- ⏸️ **Tool: `get_timing_constraints`**
  - **Purpose:** Find timing constraint examples for specific configurations
  - **Examples:**
    - "What timing constraints needed for DDR4-1600?"
    - "PCIe Gen2 clock constraints"
    - "Multi-cycle paths for CDC"
  - **Returns:** SDC/PDC constraint examples from documentation
  - **Status:** NOT STARTED

#### 2.2 Integration Testing (1 hour)

- ⏸️ **Test with Real tcl_monster Workflows**
  - Test DDR4 generator workflow
  - Test PCIe configuration validation
  - Test error resolution queries
  - Test timing constraint lookup
  - **Status:** NOT STARTED

#### 2.3 Documentation (30 min)

- ⏸️ **Create `docs/TCL_MONSTER_INTEGRATION.md`**
  - Example workflows for each IP generator (DDR4, PCIe, CCC, UART, GPIO)
  - Sample queries and expected responses
  - Best practices for using RAG in TCL generation
  - **Status:** NOT STARTED

### Phase 2 Success Criteria
- ✅ Three tcl_monster tools working and tested
- ✅ Successfully used in DDR4 and PCIe generation workflows
- ✅ Error resolution returns relevant documentation
- ✅ Timing constraints tool returns valid SDC examples
- ✅ Documentation complete with examples

### Phase 2 Deliverables
1. ⏸️ `query_ip_parameters` tool
2. ⏸️ `explain_error` tool
3. ⏸️ `get_timing_constraints` tool
4. ⏸️ Integration tests with tcl_monster
5. ⏸️ `docs/TCL_MONSTER_INTEGRATION.md`

---

## Phase 3: Advanced Features (4-6 hours, OPTIONAL)

### Objectives
- Add FastAPI REST layer for external tools
- Implement advanced search capabilities
- Optimize performance
- Add monitoring and observability

### Tasks

#### 3.1 FastAPI REST Layer (2 hours, OPTIONAL)

- ⏸️ **Port `server/app.py` from Windows Production**
  - **Target:** `~/fpga_mcp/src/fpga_rag/server/app.py`
  - **Endpoints:**
    - `/health` - Health check
    - `/search` - Semantic search with ChromaDB→SQLite fallback
    - `/documents` - List all documents
    - `/documents/{slug}/tables` - Get tables from specific doc
    - `/documents/{slug}/diagrams` - Get diagrams from specific doc
    - `/diagrams` - Browse/filter all diagrams
  - **Why:** Useful for external tools, not strictly needed for Claude Code
  - **Status:** NOT STARTED

#### 3.2 Advanced Search Tools (2 hours)

- ⏸️ **Tool: `compare_across_documents`**
  - Search multiple documents and compare approaches
  - Useful for "How does DDR4 differ between PolarFire and RT PolarFire?"
  - **Status:** NOT STARTED

- ⏸️ **Tool: `search_by_section`**
  - Search within specific sections (e.g., "Clock Distribution")
  - Preserve section hierarchy from semantic chunking
  - **Status:** NOT STARTED

- ⏸️ **Tool: `find_parameters`**
  - Extract register settings, timing parameters, pin assignments
  - Table-specific search
  - **Status:** NOT STARTED

- ⏸️ **Tool: `search_with_context`**
  - Return results with surrounding context (±2 pages)
  - Useful for understanding diagrams in context
  - **Status:** NOT STARTED

#### 3.3 Performance Optimization (1 hour)

- ⏸️ **LRU Cache for Frequent Queries**
  - Cache by query hash
  - 100-entry LRU cache
  - **Status:** NOT STARTED

- ⏸️ **Warmup on Server Start**
  - Preload embedding model
  - Test ChromaDB connection
  - Prime cache with common queries
  - **Status:** NOT STARTED

- ⏸️ **Connection Pooling**
  - Reuse ChromaDB connections
  - **Status:** NOT STARTED

#### 3.4 Monitoring & Observability (1 hour)

- ⏸️ **Query Analytics Logging**
  - Log all queries with timestamps
  - Track: query, results, duration, user satisfaction
  - **Status:** NOT STARTED

- ⏸️ **Performance Metrics**
  - p50/p95/p99 latency
  - Cache hit rate
  - ChromaDB vs fallback usage
  - **Status:** NOT STARTED

- ⏸️ **Health Check Dashboard**
  - ChromaDB status
  - Indexed document count
  - Recent query performance
  - **Status:** NOT STARTED

### Phase 3 Success Criteria
- ✅ FastAPI REST endpoints working (if implemented)
- ✅ Advanced search tools tested
- ✅ Response times <500ms (p95)
- ✅ Cache hit rate >30%
- ✅ Monitoring dashboard functional

### Phase 3 Deliverables
1. ⏸️ FastAPI REST layer (optional)
2. ⏸️ Advanced search tools (4 new tools)
3. ⏸️ Performance optimizations
4. ⏸️ Monitoring & metrics

---

## Long-Term Enhancements (1+ weeks)

### Table Content Indexing (1 week)
**Current:** Only table metadata indexed (row/col count, page number)
**Needed:** Actual table content searchable

**Example Use Case:**
```
User: "What's the maximum DDR4 frequency for MPF300-1?"
System searches table contents:
  - Table on page 47: "DDR4 Speed Grades"
  - Row: "MPF300-1" | Column: "Max Freq" | Value: "1600 MHz"
```

**Tasks:**
- Parse CSV tables into rows
- Design embedding strategy (per-row vs per-table)
- Generate embeddings for ~1000 tables
- Test and tune
- Documentation

**Time Estimate:** 15-20 hours

### Enhanced Diagram Search (1-2 weeks)
**Current:** Basic diagram browsing
**Needed:** OCR and visual similarity search

**Features:**
- OCR on diagrams (extract text from images)
- Similarity search on diagram embeddings (visual search via CLIP)
- Link diagrams to related tables/text
- Filter by diagram type (block diagram, timing diagram, pinout, etc.)

**Time Estimate:** 30-40 hours

### Protocol Knowledge Graphs (2+ weeks)
**Goal:** Understand relationships between IP cores

**Example:**
```
User: "How do I configure 10GBASE-KR?"
System understands:
  10GBASE-KR → requires PCIe transceiver → requires CCC for clock
  → shows all related configuration steps
```

**Features:**
- Extract IP dependencies from docs
- Build knowledge graph (Neo4j or similar)
- Multi-hop reasoning across documents
- Temperature-aware specs (commercial/industrial/military)

**Time Estimate:** 60+ hours

---

## Research Findings Summary

### Windows Production Server Advantages
- 3-tier architecture (MCP → FastAPI → DB)
- Rich formatting (text + images + tables)
- Automatic fallback (ChromaDB → SQLite)
- Smart resource limiting (first 3 images base64, rest URIs)
- Proven in demo environment
- 16 documents indexed (3,452 chunks)

### Local Repo Current State
- Basic MCP stub (text-only responses)
- Direct ChromaDB access (no fallback)
- Same data pipeline (extraction, indexing)
- ChromaDB persistent storage
- Designed for Claude Code direct import

### Key Patterns to Adopt
1. **Automatic Fallback:** ChromaDB → SQLite for reliability
2. **Rich Content Blocks:** text + images + tables in MCP responses
3. **Smart Resource Limiting:** Prevent response overflow with base64 limits
4. **Batch Processing:** Progress tracking for large operations
5. **Dual-Mode Support:** Works as both library and MCP server

---

## Success Metrics

### Phase 1 Complete
- MCP server quality matches Windows production
- All 27 PDFs dynamically listed
- Error handling comprehensive
- Tests passing
- Documentation complete

### Phase 2 Complete
- tcl_monster successfully using RAG for TCL generation
- Error resolution queries return relevant docs
- Parameter validation automated

### Production Ready
- Response times <500ms (p95)
- Error rates <1%
- Works on both home and work computers
- Memory MCP preserves context across sessions
- Can handle 100+ docs without degradation

---

## Time Tracking

| Phase | Estimated | Actual | Status |
|-------|-----------|--------|--------|
| Phase 1 - Documentation | 30 min | ~25 min | ✅ COMPLETE |
| Phase 1 - Port ChromaDB Adapter | 30 min | TBD | ⏳ PENDING |
| Phase 1 - Port MCP Server | 2 hours | TBD | ⏳ PENDING |
| Phase 1 - Quality Improvements | 1.5 hours | TBD | ⏳ PENDING |
| **Phase 1 TOTAL** | **3-4 hours** | **~0.5 hrs** | **⏳ IN PROGRESS** |
| Phase 2 - tcl_monster Tools | 2 hours | TBD | ⏸️ NOT STARTED |
| Phase 2 - Testing | 1 hour | TBD | ⏸️ NOT STARTED |
| Phase 2 - Documentation | 30 min | TBD | ⏸️ NOT STARTED |
| **Phase 2 TOTAL** | **3-4 hours** | **TBD** | **⏸️ NOT STARTED** |
| Phase 3 - FastAPI | 2 hours | TBD | ⏸️ OPTIONAL |
| Phase 3 - Advanced Tools | 2 hours | TBD | ⏸️ OPTIONAL |
| Phase 3 - Performance | 1 hour | TBD | ⏸️ OPTIONAL |
| Phase 3 - Monitoring | 1 hour | TBD | ⏸️ OPTIONAL |
| **Phase 3 TOTAL** | **4-6 hours** | **TBD** | **⏸️ OPTIONAL** |

**Grand Total:** 10-14 hours for Phases 1-3

---

## Next Actions

1. ✅ **DONE:** Update `.claude/CLAUDE.md`
2. ✅ **DONE:** Create this roadmap
3. **NOW:** Port `tools/chroma_adapter.py` (30 min)
4. **NEXT:** Port `tools/polarfire_mcp_server.py` (2 hrs)
5. **NEXT:** Implement quality improvements (1.5 hrs)
6. **NEXT:** Test Phase 1 (30 min)

**Current Focus:** Complete Phase 1 foundation work

---

## Notes

- Windows repo at `/mnt/c/fpga_mcp` is reference implementation
- Local repo at `~/fpga_mcp` is active development
- Both share same ChromaDB data format
- tcl_monster at `/mnt/c/tcl_monster` is primary use case
- Memory MCP should track all changes for cross-session continuity
