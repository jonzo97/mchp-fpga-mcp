#!/usr/bin/env python3
"""MCP server for FPGA documentation search.

Provides tools for searching PolarFire FPGA documentation.
"""
import sys
from pathlib import Path
from typing import Any

# Add mchp-mcp-core to path
MCHP_CORE_PATH = Path.home() / "mchp-mcp-core"
if str(MCHP_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(MCHP_CORE_PATH))

# Add fpga_mcp to path
FPGA_MCP_PATH = Path(__file__).parent.parent.parent
if str(FPGA_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(FPGA_MCP_PATH))

from mcp.server import Server
from mcp.types import Tool, TextContent
from mchp_mcp_core.storage.schemas import SearchQuery
from fpga_rag.indexing import DocumentEmbedder
from fpga_rag.config import settings

# Configure paths
fpga_mcp_root = Path.home() / "fpga_mcp"
settings.content_dir = fpga_mcp_root / "content"
settings.chroma_path = fpga_mcp_root / "chroma"

# Initialize embedder (singleton)
_embedder: DocumentEmbedder | None = None


def get_embedder() -> DocumentEmbedder:
    """Get or create the document embedder."""
    global _embedder
    if _embedder is None:
        _embedder = DocumentEmbedder()
    return _embedder


# Create MCP server
app = Server("fpga-docs")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="search_fpga_docs",
            description="Search PolarFire FPGA documentation (user guides, datasheets, app notes). "
                       "Returns relevant excerpts with page numbers and document citations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'DDR4 memory controller configuration', 'PCIe lane settings')"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 20)",
                        "default": 5
                    },
                    "document_type": {
                        "type": "string",
                        "description": "Filter by document type (optional)",
                        "enum": ["User Guide", "Datasheet", "Application Note", "Programming Guide"]
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_fpga_doc_info",
            description="Get information about indexed FPGA documentation (available documents, page counts, versions)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""

    if name == "search_fpga_docs":
        query_text = arguments.get("query", "")
        top_k = min(arguments.get("top_k", 5), 20)
        doc_type = arguments.get("document_type")

        if not query_text:
            return [TextContent(type="text", text="Error: query parameter is required")]

        # Get embedder
        embedder = get_embedder()

        if not embedder.vector_store.is_available():
            return [TextContent(
                type="text",
                text="Error: Vector store not available. ChromaDB may not be initialized."
            )]

        # Create search query
        search_query = SearchQuery(
            query=query_text,
            top_k=top_k,
            document_type=doc_type
        )

        # Search
        results = embedder.vector_store.search(search_query)

        if not results:
            return [TextContent(
                type="text",
                text=f"No results found for query: '{query_text}'"
            )]

        # Format results
        response_parts = [f"Found {len(results)} results for: '{query_text}'\n"]

        for i, result in enumerate(results, 1):
            response_parts.append(f"\n--- Result {i} (Score: {result.score:.3f}) ---")
            response_parts.append(f"Document: {result.title}")
            response_parts.append(f"Page: {result.slide_or_page}")
            response_parts.append(f"Excerpt:\n{result.snippet}")
            response_parts.append("")

        return [TextContent(type="text", text="\n".join(response_parts))]

    elif name == "get_fpga_doc_info":
        embedder = get_embedder()

        if not embedder.vector_store.is_available():
            return [TextContent(
                type="text",
                text="Error: Vector store not available"
            )]

        # Get collection info
        info = embedder.vector_store.get_collection_info()

        response = f"""FPGA Documentation Database Info:

Collection: {info.get('name', 'Unknown')}
Total indexed chunks: {info.get('points_count', 0):,}
Storage path: {info.get('path', 'Unknown')}

Documents available:
- PolarFire FPGA Memory Controller User Guide (189 pages)
- PolarFire FPGA Transceiver User Guide (158 pages)
- PolarFire FPGA User IO User Guide (147 pages)
- PolarFire FPGA Fabric User Guide (125 pages)
- PolarFire FPGA Datasheet (100 pages)
- PolarFire FPGA Clocking Resources User Guide (71 pages)
- PolarFire FPGA Board Design User Guide (38 pages)

Use search_fpga_docs to query this documentation.
"""

        return [TextContent(type="text", text=response)]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
