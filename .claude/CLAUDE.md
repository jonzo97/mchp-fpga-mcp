# FPGA Documentation RAG System - Dual Mode Support

## CRITICAL - READ THIS FIRST

**THIS PROJECT SUPPORTS BOTH CLAUDE CODE (PRIMARY) AND CLAUDE DESKTOP (SECONDARY)**

This is a documentation ingestion and search system for PolarFire FPGA documentation that supports:
1. **Claude Code (CLI)** - Direct Python imports (primary usage)
2. **Claude Desktop** - MCP server protocol (for GUI users)
3. **tcl_monster integration** - Libero TCL automation toolkit support

### Usage Modes

**Mode 1: Claude Code Direct Import (PRIMARY)**
- ✅ Import `fpga_rag` as Python library
- ✅ Local ChromaDB vector database at `~/fpga_mcp/chroma`
- ✅ Direct function calls, no MCP protocol needed
- ✅ Fastest performance, lowest latency

**Mode 2: Claude Desktop MCP Server (SECONDARY)**
- ✅ MCP protocol via stdio
- ✅ Rich content formatting (text + images + tables)
- ✅ GUI-friendly responses with base64 images
- ✅ Useful for non-technical users

**Mode 3: tcl_monster Integration (SPECIALIZED)**
- ✅ Query IP parameters for TCL generation
- ✅ Validate FPGA configurations
- ✅ Resolve Libero error messages
- ✅ Timing constraint examples

## Usage Pattern for Claude Code

When the user asks to generate TCL scripts or FPGA designs:

```python
# Import the search tools directly
import sys
sys.path.insert(0, "/home/jorgill/fpga_mcp/src")
from fpga_rag.indexing import DocumentEmbedder
from mchp_mcp_core.storage.schemas import SearchQuery

# Initialize (uses existing ChromaDB)
embedder = DocumentEmbedder()

# Search documentation
results = embedder.vector_store.search(
    SearchQuery(query="DDR4 controller configuration", top_k=3)
)

# Use results to inform TCL generation
for result in results:
    print(f"{result.title} (Page {result.slide_or_page})")
    print(result.snippet)
```

## Project Structure

```
~/fpga_mcp/
├── content/              # Extracted text from 27 PolarFire PDFs
├── chroma/              # ChromaDB vector database (DO NOT DELETE)
├── src/fpga_rag/
│   ├── extraction/      # PDF extraction pipeline
│   ├── indexing/        # Embedding generation and ChromaDB indexing
│   ├── mcp_server/      # MCP server for Claude Desktop
│   ├── server/          # FastAPI REST layer (optional)
│   ├── storage/         # ChromaDB adapters and schemas
│   ├── utils/           # Text cleaning, hashing, token counting
│   └── config.py        # Central configuration
├── scripts/
│   ├── test_extraction.py
│   └── test_indexing.py
└── docs/
    └── IMPROVEMENTS_ROADMAP.md  # Development roadmap
```

## Indexed Documents (27 PDFs total)

### Core Documentation (Original 7)
1. PolarFire FPGA Memory Controller User Guide (189 pages)
2. PolarFire FPGA Transceiver User Guide (158 pages)
3. PolarFire FPGA User IO User Guide (147 pages)
4. PolarFire FPGA Fabric User Guide (125 pages)
5. PolarFire FPGA Datasheet (100 pages)
6. PolarFire FPGA Clocking Resources User Guide (71 pages)
7. PolarFire FPGA Board Design User Guide (38 pages)

### Additional Documentation (+20)
8. Cryptoprocessor Security Implementation
9. Power-Up and Reset User Guide
10. Security User Guide
11. Auto Update Guide
12. Evaluation Kit User Guide
13. Low Power Design Guide
14. Transceiver DFE Guide
15. Transceiver Demo Guide
16. Programming User Guide
17. SFP+ Module Application Note
18. Safety-Critical Application Note
19. PolarFire SoC Design Flow
20. Discovery Kit User Guide
21. Discovery Kit QuickStart
22. DSP FIR Filter Application Note
23. RT PolarFire 1G Ethernet Loopback
24. RT PolarFire Datasheet
25. RT PolarFire Programming Guide
26. RT PolarFire Lockstep Processor
27. RT PolarFire RISC-V Subsystem

## Related Project: tcl_monster

This RAG system feeds into `/mnt/c/tcl_monster` (Libero FPGA automation toolkit) by providing documentation context when Claude Code generates TCL scripts.

### tcl_monster Integration Examples

**Use Case 1: DDR4 Configuration**
```python
# Before generating DDR4 TCL script, query specs
results = embedder.vector_store.search(SearchQuery(
    query="DDR4 timing parameters tRAS tRC tRCD industrial temperature 4GB",
    top_k=5
))

# Use results to validate/inform TCL generation
for result in results:
    print(f"Spec from {result.title} page {result.slide_or_page}:")
    print(result.snippet)
```

**Use Case 2: PCIe Validation**
```python
# Verify PCIe endpoint configuration
results = embedder.vector_store.search(SearchQuery(
    query="PCIe Gen2 x4 lane configuration MPF300 transceiver settings",
    top_k=3
))
```

**Use Case 3: Error Resolution**
```python
# Libero build failed with timing error
error_msg = "Critical Warning: Clock domain CDC violation"
results = embedder.vector_store.search(SearchQuery(
    query=f"clock domain crossing CDC constraints {error_msg}",
    top_k=5
))

# Suggest fixes based on documentation
print("Potential solutions from PolarFire documentation:")
for result in results:
    print(f"- {result.title} (Page {result.slide_or_page})")
    print(f"  {result.snippet}\n")
```

## MCP Server Usage (Claude Desktop)

**Starting the MCP Server:**
```bash
python src/fpga_rag/mcp_server/server.py
```

**Claude Desktop Configuration:**
```json
{
  "mcpServers": {
    "fpga-docs": {
      "command": "python",
      "args": ["/home/jorgill/fpga_mcp/src/fpga_rag/mcp_server/server.py"],
      "env": {
        "FPGA_RAG_CHROMA_PATH": "/home/jorgill/fpga_mcp/chroma",
        "FPGA_RAG_CONTENT_DIR": "/home/jorgill/fpga_mcp/content"
      }
    }
  }
}
```

**Available Tools:**
- `search_fpga_docs` - Semantic search with rich content (text + images + tables)
- `polarfire_browse_diagrams` - Filter/browse diagrams by document, caption, dimensions
- `get_fpga_doc_info` - Collection metadata and statistics

## When Adding New Documentation

1. Place PDFs in `~/fpga_mcp/` root
2. Run extraction: `python scripts/test_extraction.py`
3. Run indexing: `python scripts/test_indexing.py`
4. Search becomes available immediately

## Architecture & Performance

**Current Status:**
- **Documents:** 27 PDFs indexed (Original 7 + 20 additional)
- **Vector Database:** ChromaDB at `~/fpga_mcp/chroma`
- **Embedding Model:** sentence-transformers (via mchp-mcp-core)
- **Chunking:** Semantic chunking with token limits (1500 tokens max)
- **Search:** Vector similarity + metadata filtering

**Performance Characteristics:**
- **Direct Import (Claude Code):** 200-300ms query time
- **MCP Server (Claude Desktop):** 300-500ms query time (includes formatting)
- **Fallback:** SQLite-based search if ChromaDB unavailable

## Development Roadmap

See `docs/IMPROVEMENTS_ROADMAP.md` for:
- Phase 1: Foundation improvements (error handling, logging, testing)
- Phase 2: tcl_monster-specific tools (IP parameters, error explanation)
- Phase 3: Advanced features (table content search, diagram OCR)

## Context for Future Sessions

**Purpose:** Make Claude Code smarter when helping with FPGA/Libero TCL automation in the `tcl_monster` project.

**Key Integration Points:**
1. **DDR4 Generator:** Query timing parameters and configuration specs
2. **PCIe Generator:** Validate lane configurations and transceiver settings
3. **CCC Generator:** Lookup PLL multiplier/divider constraints
4. **Error Resolution:** Search docs for Libero error explanations
5. **Timing Constraints:** Find SDC/PDC constraint examples

**Production Deployment:**
- Windows production server at `/mnt/c/fpga_mcp` (reference implementation)
- Local development at `~/fpga_mcp` (active development)
- Both repos share same ChromaDB data format
