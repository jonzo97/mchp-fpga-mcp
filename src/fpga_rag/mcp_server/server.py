#!/usr/bin/env python3
"""MCP server for FPGA documentation search.

Production-ready server with rich content formatting (text + images + tables).
Supports both Claude Code (direct import) and Claude Desktop (MCP protocol).

Features:
- Semantic search with ChromaDB
- Rich content blocks (text, images, tables)
- Dynamic document catalog
- Comprehensive error handling
- Structured logging
"""
import base64
import csv
import logging
import sys
from pathlib import Path
from typing import Any, List, Optional

# Add mchp-mcp-core to path
MCHP_CORE_PATH = Path.home() / "mchp-mcp-core"
if str(MCHP_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(MCHP_CORE_PATH))

# Add fpga_mcp to path
FPGA_MCP_PATH = Path(__file__).parent.parent.parent
if str(FPGA_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(FPGA_MCP_PATH))

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent, ImageContent, Resource
    from mcp import server as mcp_server
except ImportError as e:
    print(f"ERROR: MCP Python SDK not installed: {e}", file=sys.stderr)
    print("Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

try:
    from mchp_mcp_core.storage.schemas import SearchQuery
    from fpga_rag.indexing import DocumentEmbedder
    from fpga_rag.config import settings
except ImportError as e:
    print(f"ERROR: Required modules not found: {e}", file=sys.stderr)
    print("Make sure fpga_rag and mchp-mcp-core are properly installed", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)  # Log to stderr to not interfere with MCP stdio
    ]
)
logger = logging.getLogger(__name__)

# Configure paths
fpga_mcp_root = Path.home() / "fpga_mcp"
settings.content_dir = fpga_mcp_root / "content"
settings.chroma_path = fpga_mcp_root / "chroma"

# Initialize embedder (singleton)
_embedder: Optional[DocumentEmbedder] = None


def get_embedder() -> DocumentEmbedder:
    """Get or create the document embedder (singleton pattern).

    Returns:
        DocumentEmbedder instance

    Raises:
        RuntimeError: If embedder cannot be initialized
    """
    global _embedder
    if _embedder is None:
        logger.info("Initializing DocumentEmbedder...")
        try:
            _embedder = DocumentEmbedder()
            logger.info("✅ DocumentEmbedder initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize DocumentEmbedder: {e}")
            raise RuntimeError(f"Failed to initialize document embedder: {e}")
    return _embedder


def read_csv_as_markdown(csv_path: str | Path, max_rows: int = 10) -> str:
    """Convert a CSV file to a markdown table.

    Args:
        csv_path: Path to CSV file
        max_rows: Maximum rows to include (default: 10)

    Returns:
        Markdown-formatted table string
    """
    try:
        full_path = Path(csv_path)
        if not full_path.exists():
            return f"*Table not found: {csv_path}*"

        with open(full_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return "*Empty table*"

        # Limit to first N rows for display
        display_rows = rows[:max_rows]
        has_more = len(rows) > max_rows

        # Build markdown table
        lines = []
        if display_rows:
            # Header
            lines.append("| " + " | ".join(str(cell) for cell in display_rows[0]) + " |")
            lines.append("| " + " | ".join("---" for _ in display_rows[0]) + " |")
            # Data rows
            for row in display_rows[1:]:
                lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
            if has_more:
                lines.append(f"\n*({len(rows) - max_rows} more rows...)*")

        return "\n".join(lines)
    except Exception as exc:
        logger.error(f"Error reading CSV {csv_path}: {exc}")
        return f"*Error reading table: {exc}*"


def encode_image_base64(image_path: str | Path) -> str:
    """Read an image file and encode it as base64.

    Args:
        image_path: Path to image file

    Returns:
        Base64-encoded string, or empty string if error
    """
    try:
        full_path = Path(image_path)
        if not full_path.exists():
            logger.warning(f"Image not found: {image_path}")
            return ""

        with open(full_path, 'rb') as f:
            image_data = f.read()

        return base64.b64encode(image_data).decode('utf-8')
    except Exception as exc:
        logger.error(f"Error encoding image {image_path}: {exc}")
        return ""


def get_dynamic_document_catalog() -> List[dict]:
    """Query ChromaDB to get list of indexed documents dynamically.

    Returns:
        List of dicts with document info (doc_id, title, page_count)
    """
    try:
        embedder = get_embedder()

        if not embedder.vector_store.is_available():
            logger.warning("Vector store not available for catalog query")
            return []

        # Query ChromaDB for all unique documents
        results = embedder.vector_store.collection.get(
            include=["metadatas"]
        )

        if not results or not results.get('metadatas'):
            return []

        # Extract unique documents and their page ranges
        docs = {}
        for meta in results['metadatas']:
            doc_id = meta.get('doc_id', 'unknown')
            title = meta.get('title', doc_id)
            page = meta.get('slide_or_page', 0)

            if doc_id not in docs:
                docs[doc_id] = {
                    'doc_id': doc_id,
                    'title': title,
                    'pages': set()
                }
            docs[doc_id]['pages'].add(page)

        # Format as list sorted by document name
        catalog = [
            {
                'doc_id': doc_id,
                'title': data['title'],
                'page_count': len(data['pages']),
                'page_range': f"{min(data['pages'])}-{max(data['pages'])}" if data['pages'] else "N/A"
            }
            for doc_id, data in sorted(docs.items())
        ]

        logger.info(f"Generated dynamic catalog: {len(catalog)} documents")
        return catalog

    except Exception as e:
        logger.error(f"Failed to generate document catalog: {e}")
        return []


# Create MCP server
app = Server("fpga-docs")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available MCP tools.

    Returns:
        List of Tool objects
    """
    return [
        Tool(
            name="search_fpga_docs",
            description="Search PolarFire FPGA documentation (user guides, datasheets, app notes). "
                       "Returns relevant excerpts with page numbers, document citations, and related content. "
                       "Includes diagrams and tables when available.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query (e.g., 'DDR4 memory controller configuration', "
                                     "'PCIe Gen2 lane settings', 'CCC PLL multiplier constraints')"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 20)",
                        "minimum": 1,
                        "maximum": 20,
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
            description="Get information about indexed FPGA documentation. "
                       "Returns list of available documents, page counts, and collection statistics. "
                       "Dynamically updated as new documents are indexed.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="query_ip_parameters",
            description="Query IP core parameters and configuration options for Libero TCL generation. "
                       "Specialized for tcl_monster integration. Returns parameter specifications, "
                       "valid ranges, default values, and configuration examples.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip_core": {
                        "type": "string",
                        "description": "IP core name (e.g., 'PF_DDR4', 'PF_CCC', 'PF_PCIE', 'CoreUARTapb', 'CoreGPIO')"
                    },
                    "parameter": {
                        "type": "string",
                        "description": "Specific parameter to query (optional). If omitted, returns all parameters for the IP core."
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 10)",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5
                    }
                },
                "required": ["ip_core"]
            }
        ),
        Tool(
            name="explain_error",
            description="Parse Libero error messages and search documentation for solutions. "
                       "Specialized for tcl_monster error resolution. Returns potential fixes, "
                       "related documentation sections, and configuration recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "error_message": {
                        "type": "string",
                        "description": "Libero error message or warning text (e.g., 'Critical Warning: Clock domain CDC violation', "
                                     "'Error: Insufficient PLL resources', 'Timing constraint not met')"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context about what was being done when error occurred (optional)"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of potential solutions to return (default: 5, max: 10)",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5
                    }
                },
                "required": ["error_message"]
            }
        ),
        Tool(
            name="get_timing_constraints",
            description="Find timing constraint examples (SDC/PDC) for specific FPGA configurations. "
                       "Specialized for tcl_monster timing constraint generation. Returns constraint "
                       "examples, clock definitions, and timing requirements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "constraint_type": {
                        "type": "string",
                        "description": "Type of constraint needed (e.g., 'clock definition', 'input/output delay', "
                                     "'multi-cycle path', 'false path', 'clock domain crossing')"
                    },
                    "ip_or_interface": {
                        "type": "string",
                        "description": "IP core or interface the constraint applies to (e.g., 'DDR4', 'PCIe', 'UART', 'CCC')"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of examples to return (default: 3, max: 10)",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 3
                    }
                },
                "required": ["constraint_type"]
            }
        ),
        # Note: polarfire_browse_diagrams will be added when diagram extraction is implemented
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls with comprehensive error handling and logging.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        List of TextContent objects
    """
    import time
    start_time = time.time()

    logger.info(f"Tool called: {name} with arguments: {arguments}")

    try:
        if name == "search_fpga_docs":
            result = await handle_search_tool(arguments)

        elif name == "get_fpga_doc_info":
            result = await handle_doc_info_tool(arguments)

        elif name == "query_ip_parameters":
            result = await handle_query_ip_parameters(arguments)

        elif name == "explain_error":
            result = await handle_explain_error(arguments)

        elif name == "get_timing_constraints":
            result = await handle_get_timing_constraints(arguments)

        else:
            logger.warning(f"Unknown tool requested: {name}")
            return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

        duration = time.time() - start_time
        logger.info(f"Tool {name} completed in {duration:.2f}s")
        return result

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Tool {name} failed after {duration:.2f}s: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error executing tool '{name}': {str(e)}\n\n"
                 f"Please check the logs for more details."
        )]


async def handle_search_tool(arguments: dict) -> List[TextContent]:
    """Handle search_fpga_docs tool call.

    Args:
        arguments: Search parameters (query, top_k, document_type)

    Returns:
        List of content blocks (text, images, tables)
    """
    # Validate arguments
    query_text = arguments.get("query", "")
    if not query_text or not query_text.strip():
        return [TextContent(type="text", text="Error: 'query' parameter is required and cannot be empty")]

    top_k = arguments.get("top_k", 5)
    if not isinstance(top_k, int) or not (1 <= top_k <= 20):
        return [TextContent(type="text", text="Error: 'top_k' must be an integer between 1 and 20")]

    doc_type = arguments.get("document_type")

    # Get embedder
    try:
        embedder = get_embedder()
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Error: {e}")]

    # Check vector store availability
    if not embedder.vector_store.is_available():
        return [TextContent(
            type="text",
            text="Error: Vector store not available. ChromaDB may not be initialized.\n\n"
                 "Please run the indexing pipeline first:\n"
                 "  python scripts/test_indexing.py"
        )]

    # Create search query
    search_query = SearchQuery(
        query=query_text,
        top_k=top_k,
        document_type=doc_type
    )

    # Execute search
    logger.info(f"Searching for: '{query_text}' (top_k={top_k})")
    results = embedder.vector_store.search(search_query)

    if not results:
        return [TextContent(
            type="text",
            text=f"No results found for query: '{query_text}'\n\n"
                 f"Try:\n"
                 f"- Using different keywords\n"
                 f"- Broadening your search terms\n"
                 f"- Checking spelling"
        )]

    # Format results as rich content
    logger.info(f"Found {len(results)} results, formatting...")
    content_blocks = format_search_results_rich(results, query_text)

    return content_blocks


async def handle_doc_info_tool(arguments: dict) -> List[TextContent]:
    """Handle get_fpga_doc_info tool call.

    Args:
        arguments: Empty dict (no parameters)

    Returns:
        List with single TextContent containing document info
    """
    try:
        embedder = get_embedder()
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Error: {e}")]

    if not embedder.vector_store.is_available():
        return [TextContent(
            type="text",
            text="Error: Vector store not available"
        )]

    # Get collection info
    info = embedder.vector_store.get_collection_info()

    # Get dynamic document catalog
    catalog = get_dynamic_document_catalog()

    # Format response
    response_lines = [
        "# FPGA Documentation Database Info\n",
        f"**Collection:** {info.get('name', 'Unknown')}",
        f"**Total indexed chunks:** {info.get('points_count', 0):,}",
        f"**Storage path:** {info.get('path', 'Unknown')}",
        f"**Documents indexed:** {len(catalog)}",
        "\n## Indexed Documents\n"
    ]

    if catalog:
        for doc in catalog:
            response_lines.append(
                f"- **{doc['title']}** ({doc['page_count']} pages, range: {doc['page_range']})"
            )
    else:
        response_lines.append("*(No documents in catalog - database may be empty)*")

    response_lines.extend([
        "\n## Usage",
        "Use `search_fpga_docs` to query this documentation with natural language.",
        "\n**Example queries:**",
        "- 'DDR4 memory controller initialization sequence'",
        "- 'PCIe Gen2 x4 transceiver configuration'",
        "- 'CCC PLL settings for 50MHz output'",
        "- 'Timing constraints for clock domain crossing'",
    ])

    response = "\n".join(response_lines)
    return [TextContent(type="text", text=response)]


async def handle_query_ip_parameters(arguments: dict) -> List[TextContent]:
    """Handle query_ip_parameters tool call.

    Searches documentation for IP core parameters, configuration options,
    valid ranges, and examples. Optimized for TCL generation in tcl_monster.

    Args:
        arguments: ip_core (required), parameter (optional), top_k (optional)

    Returns:
        List of content blocks with parameter information
    """
    # Validate arguments
    ip_core = arguments.get("ip_core", "")
    if not ip_core or not ip_core.strip():
        return [TextContent(type="text", text="Error: 'ip_core' parameter is required")]

    parameter = arguments.get("parameter", "")
    top_k = arguments.get("top_k", 5)

    # Get embedder
    try:
        embedder = get_embedder()
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Error: {e}")]

    # Check vector store availability
    if not embedder.vector_store.is_available():
        return [TextContent(
            type="text",
            text="Error: Vector store not available. Please run indexing first."
        )]

    # Build search query
    if parameter:
        query_text = f"{ip_core} {parameter} parameter configuration valid values range"
    else:
        query_text = f"{ip_core} IP core parameters configuration options"

    logger.info(f"Querying IP parameters: {ip_core}, parameter={parameter}")

    # Execute search
    search_query = SearchQuery(query=query_text, top_k=top_k)
    results = embedder.vector_store.search(search_query)

    if not results:
        return [TextContent(
            type="text",
            text=f"No parameter information found for IP core: '{ip_core}'\n\n"
                 f"Suggestions:\n"
                 f"- Verify IP core name (e.g., PF_DDR4, PF_CCC, PF_PCIE)\n"
                 f"- Try a more general search without specific parameter\n"
                 f"- Check if documentation for this IP is indexed"
        )]

    # Format results with focus on parameters
    summary_lines = [
        f"# IP Parameters: {ip_core}\n",
    ]

    if parameter:
        summary_lines.append(f"**Specific Parameter:** {parameter}\n")

    summary_lines.append(f"Found {len(results)} relevant configuration sections\n")
    summary_lines.append("---\n")

    for idx, result in enumerate(results, start=1):
        title = result.title or "Unknown Document"
        page = result.slide_or_page or "?"
        snippet = result.snippet or result.text or ""

        summary_lines.append(f"## Configuration {idx}: {title} (Page {page})\n")

        # Highlight parameter-related content
        if snippet:
            max_length = 600
            if len(snippet) > max_length:
                snippet = snippet[:max_length] + "..."
            summary_lines.append(f"```\n{snippet}\n```\n")

        summary_lines.append("---\n")

    summary_lines.extend([
        "\n## Next Steps for TCL Generation",
        "1. Review parameter ranges and valid values",
        "2. Check for dependencies between parameters",
        "3. Note any required vs. optional parameters",
        "4. Verify default values if not specified",
    ])

    response = "\n".join(summary_lines)
    return [TextContent(type="text", text=response)]


async def handle_explain_error(arguments: dict) -> List[TextContent]:
    """Handle explain_error tool call.

    Searches documentation for solutions to Libero error messages.
    Provides potential fixes, related sections, and recommendations.

    Args:
        arguments: error_message (required), context (optional), top_k (optional)

    Returns:
        List of content blocks with error solutions
    """
    # Validate arguments
    error_message = arguments.get("error_message", "")
    if not error_message or not error_message.strip():
        return [TextContent(type="text", text="Error: 'error_message' parameter is required")]

    context = arguments.get("context", "")
    top_k = arguments.get("top_k", 5)

    # Get embedder
    try:
        embedder = get_embedder()
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Error: {e}")]

    # Check vector store availability
    if not embedder.vector_store.is_available():
        return [TextContent(
            type="text",
            text="Error: Vector store not available. Please run indexing first."
        )]

    # Build search query - extract key terms from error
    # Common error patterns: timing, constraints, resources, clock, CDC, etc.
    query_text = error_message

    if context:
        query_text += f" {context}"

    # Add common solution keywords
    query_text += " solution fix constraint configuration requirements"

    logger.info(f"Searching for error solution: {error_message[:100]}...")

    # Execute search
    search_query = SearchQuery(query=query_text, top_k=top_k)
    results = embedder.vector_store.search(search_query)

    if not results:
        return [TextContent(
            type="text",
            text=f"No solutions found for error: '{error_message[:100]}...'\n\n"
                 f"Suggestions:\n"
                 f"- Try simplifying the error message to key terms\n"
                 f"- Search for general topics (e.g., 'timing constraints', 'clock domain crossing')\n"
                 f"- Provide additional context about what was being configured"
        )]

    # Format results with focus on solutions
    summary_lines = [
        f"# Error Resolution\n",
        f"**Error:** {error_message}\n",
    ]

    if context:
        summary_lines.append(f"**Context:** {context}\n")

    summary_lines.append(f"\nFound {len(results)} potentially relevant sections\n")
    summary_lines.append("---\n")

    for idx, result in enumerate(results, start=1):
        title = result.title or "Unknown Document"
        page = result.slide_or_page or "?"
        score = result.score if hasattr(result, 'score') else 0.0
        snippet = result.snippet or result.text or ""

        summary_lines.append(f"## Solution {idx}: {title} (Page {page})")
        summary_lines.append(f"**Relevance:** {score:.2f}\n")

        if snippet:
            max_length = 600
            if len(snippet) > max_length:
                snippet = snippet[:max_length] + "..."
            summary_lines.append(f"```\n{snippet}\n```\n")

        summary_lines.append("---\n")

    summary_lines.extend([
        "\n## Troubleshooting Steps",
        "1. Review each solution section for applicable fixes",
        "2. Check configuration parameters mentioned",
        "3. Verify timing constraints if error is timing-related",
        "4. Consider design changes if constraints cannot be met",
        "5. Consult full document sections for detailed guidance",
    ])

    response = "\n".join(summary_lines)
    return [TextContent(type="text", text=response)]


async def handle_get_timing_constraints(arguments: dict) -> List[TextContent]:
    """Handle get_timing_constraints tool call.

    Searches documentation for timing constraint examples (SDC/PDC).
    Returns constraint syntax, clock definitions, and timing requirements.

    Args:
        arguments: constraint_type (required), ip_or_interface (optional), top_k (optional)

    Returns:
        List of content blocks with constraint examples
    """
    # Validate arguments
    constraint_type = arguments.get("constraint_type", "")
    if not constraint_type or not constraint_type.strip():
        return [TextContent(type="text", text="Error: 'constraint_type' parameter is required")]

    ip_or_interface = arguments.get("ip_or_interface", "")
    top_k = arguments.get("top_k", 3)

    # Get embedder
    try:
        embedder = get_embedder()
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Error: {e}")]

    # Check vector store availability
    if not embedder.vector_store.is_available():
        return [TextContent(
            type="text",
            text="Error: Vector store not available. Please run indexing first."
        )]

    # Build search query
    query_text = f"timing constraint {constraint_type} SDC PDC"

    if ip_or_interface:
        query_text += f" {ip_or_interface}"

    query_text += " example syntax clock definition"

    logger.info(f"Searching timing constraints: {constraint_type}, IP={ip_or_interface}")

    # Execute search
    search_query = SearchQuery(query=query_text, top_k=top_k)
    results = embedder.vector_store.search(search_query)

    if not results:
        return [TextContent(
            type="text",
            text=f"No timing constraint examples found for: '{constraint_type}'\n\n"
                 f"Suggestions:\n"
                 f"- Try general terms like 'clock definition' or 'timing constraint'\n"
                 f"- Search for specific IP core timing requirements\n"
                 f"- Look for 'SDC' or 'PDC' constraint examples"
        )]

    # Format results with focus on constraints
    summary_lines = [
        f"# Timing Constraints: {constraint_type}\n",
    ]

    if ip_or_interface:
        summary_lines.append(f"**IP/Interface:** {ip_or_interface}\n")

    summary_lines.append(f"\nFound {len(results)} constraint examples\n")
    summary_lines.append("---\n")

    for idx, result in enumerate(results, start=1):
        title = result.title or "Unknown Document"
        page = result.slide_or_page or "?"
        snippet = result.snippet or result.text or ""

        summary_lines.append(f"## Example {idx}: {title} (Page {page})\n")

        if snippet:
            max_length = 700  # Longer for constraint examples
            if len(snippet) > max_length:
                snippet = snippet[:max_length] + "..."
            summary_lines.append(f"```\n{snippet}\n```\n")

        summary_lines.append("---\n")

    summary_lines.extend([
        "\n## Constraint Application Guidelines",
        "1. Review constraint syntax carefully (SDC vs PDC)",
        "2. Verify clock names match your design",
        "3. Adjust timing values based on your requirements",
        "4. Test constraints with timing analysis",
        "5. Consider clock domain crossings and CDC constraints",
    ])

    response = "\n".join(summary_lines)
    return [TextContent(type="text", text=response)]


def format_search_results_rich(results: List[Any], query: str) -> List[TextContent]:
    """Format search results as rich MCP content blocks.

    Args:
        results: List of search result objects
        query: Original search query

    Returns:
        List of content blocks (text, images, tables)
    """
    content_blocks = []

    # Summary header
    summary_lines = [
        f"# Search Results for: '{query}'\n",
        f"Found {len(results)} relevant passages\n",
        "---\n"
    ]

    for idx, result in enumerate(results, start=1):
        # Extract result fields
        title = result.title or "Unknown Document"
        page = result.slide_or_page or "?"
        score = result.score if hasattr(result, 'score') else 0.0
        snippet = result.snippet or result.text or ""
        section = result.section if hasattr(result, 'section') else ""

        # Format result header
        summary_lines.append(f"## Result {idx}: {title}")
        summary_lines.append(f"**Page:** {page}  ")
        if section:
            summary_lines.append(f"**Section:** {section}  ")
        summary_lines.append(f"**Relevance Score:** {score:.3f}\n")

        # Add snippet
        if snippet:
            # Limit snippet length to avoid overwhelming output
            max_snippet_length = 500
            if len(snippet) > max_snippet_length:
                snippet = snippet[:max_snippet_length] + "..."
            summary_lines.append(f"```\n{snippet}\n```\n")

        # Check for tables (if metadata includes table info)
        if hasattr(result, 'metadata') and isinstance(result.metadata, dict):
            tables = result.metadata.get('tables', [])
            for table_idx, table in enumerate(tables[:3], start=1):  # Limit to 3 tables per result
                csv_path = table.get('csv_path')
                if csv_path:
                    summary_lines.append(f"\n### Table {table_idx}")
                    table_md = read_csv_as_markdown(csv_path)
                    summary_lines.append(table_md + "\n")

        summary_lines.append("---\n")

    # Add summary as first content block
    content_blocks.append(TextContent(
        type="text",
        text="\n".join(summary_lines)
    ))

    # TODO: Add diagram images when diagram extraction is implemented
    # For now, diagrams are not available in local repo

    return content_blocks


async def main():
    """Run the MCP server via stdio.

    This server communicates with Claude Desktop (or other MCP clients)
    via stdin/stdout using the MCP protocol.
    """
    logger.info("Starting FPGA Documentation MCP server...")
    logger.info(f"Content directory: {settings.content_dir}")
    logger.info(f"ChromaDB path: {settings.chroma_path}")

    try:
        # Import stdio server
        from mcp.server.stdio import stdio_server

        # Run server
        async with stdio_server() as (read_stream, write_stream):
            logger.info("✅ MCP server started successfully")
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"❌ Server failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
