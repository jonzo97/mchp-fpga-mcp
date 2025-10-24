# FPGA Documentation RAG System - For Claude Code CLI

## CRITICAL - READ THIS FIRST

**THIS PROJECT IS FOR CLAUDE CODE (CLI TOOL), NOT CLAUDE DESKTOP**

This is a documentation ingestion and search system that allows Claude Code (the command-line tool you're running in) to search PolarFire FPGA documentation when generating TCL scripts and FPGA designs.

### What This Is NOT:
- ❌ NOT for Claude Desktop
- ❌ NOT an MCP server for external tools
- ❌ DO NOT touch `~/.config/Claude/claude_desktop_config.json` EVER

### What This IS:
- ✅ Python library for Claude Code to import directly
- ✅ Local ChromaDB vector database at `~/fpga_mcp/chroma`
- ✅ Search tools that Claude Code calls via Python imports
- ✅ Documentation to help generate better TCL scripts for Libero

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
├── content/              # Extracted text from 7 PolarFire PDFs (828 pages)
├── chroma/              # ChromaDB vector database (DO NOT DELETE)
├── src/fpga_rag/
│   ├── extraction/      # PDF extraction pipeline
│   ├── indexing/        # Embedding generation and ChromaDB indexing
│   ├── mcp_server/      # IGNORE - this was a mistake, not used
│   └── config.py
└── scripts/
    ├── test_extraction.py
    └── test_indexing.py
```

## Indexed Documents (828 pages total)

1. PolarFire FPGA Memory Controller User Guide (189 pages)
2. PolarFire FPGA Transceiver User Guide (158 pages)
3. PolarFire FPGA User IO User Guide (147 pages)
4. PolarFire FPGA Fabric User Guide (125 pages)
5. PolarFire FPGA Datasheet (100 pages)
6. PolarFire FPGA Clocking Resources User Guide (71 pages)
7. PolarFire FPGA Board Design User Guide (38 pages)

## Related Project: tcl_monster

This RAG system feeds into `~/tcl_monster` (Libero FPGA automation toolkit) by providing documentation context when Claude Code generates TCL scripts.

## DO NOT Create MCP Servers

The MCP server code in `mcp_server/` should be IGNORED. It was created by mistake. Claude Code doesn't need MCP - it just imports Python modules directly.

## When Adding New Documentation

1. Place PDFs in `~/fpga_mcp/` root
2. Run extraction: `python scripts/test_extraction.py`
3. Run indexing: `python scripts/test_indexing.py`
4. Search becomes available immediately

## Context for Future Sessions

This system exists to make Claude Code smarter when helping with FPGA/Libero TCL automation in the `tcl_monster` project. It's a local knowledge base, not a network service.
