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
        Tool(
            name="validate_ip_configuration",
            description="PRE-VALIDATE IP core configuration parameters against documentation BEFORE TCL generation. "
                       "Prevents build failures by checking parameter validity, ranges, and device compatibility. "
                       "Critical for tcl_monster workflow - validates configs before synthesis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip_core": {
                        "type": "string",
                        "description": "IP core name (e.g., 'PF_DDR4', 'PF_CCC', 'PF_PCIE', 'CoreUARTapb')"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Configuration parameters to validate as key-value pairs. "
                                     "Examples: {'speed': 'DDR4-2400', 'size': '4GB', 'width': '32'} for DDR4, "
                                     "{'lanes': '4', 'gen': '2'} for PCIe, {'freq_out': '100MHz'} for CCC",
                        "additionalProperties": True
                    },
                    "device": {
                        "type": "string",
                        "description": "Target device family (optional, e.g., 'MPF300', 'MPF500', 'RTPF500'). "
                                     "Used to check device-specific limitations."
                    }
                },
                "required": ["ip_core", "parameters"]
            }
        ),
        Tool(
            name="get_ip_dependencies",
            description="Identify required IP cores, clocks, interfaces, and pin requirements for a given IP. "
                       "Prevents incomplete system designs by documenting all dependencies BEFORE implementation. "
                       "Critical for system planning in tcl_monster workflows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip_core": {
                        "type": "string",
                        "description": "Primary IP core to analyze (e.g., 'PF_DDR4', 'PF_PCIE', 'MI-V', 'CoreUARTapb')"
                    },
                    "use_case": {
                        "type": "string",
                        "description": "Optional use case context (e.g., 'processor system', 'data acquisition', 'PCIe endpoint'). "
                                     "Helps find relevant integration examples."
                    }
                },
                "required": ["ip_core"]
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

        elif name == "validate_ip_configuration":
            result = await handle_validate_ip_configuration(arguments)

        elif name == "get_ip_dependencies":
            result = await handle_get_ip_dependencies(arguments)

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


async def handle_validate_ip_configuration(arguments: dict) -> List[TextContent]:
    """Handle validate_ip_configuration tool call.

    Pre-validates IP core configuration parameters against documentation
    before TCL generation. This is CRITICAL for preventing build failures.

    Args:
        arguments: ip_core (required), parameters (required dict), device (optional)

    Returns:
        List of content blocks with validation results (errors, warnings, valid params)
    """
    # Validate arguments
    ip_core = arguments.get("ip_core", "")
    if not ip_core or not ip_core.strip():
        return [TextContent(type="text", text="Error: 'ip_core' parameter is required")]

    parameters = arguments.get("parameters", {})
    if not isinstance(parameters, dict) or not parameters:
        return [TextContent(type="text", text="Error: 'parameters' must be a non-empty dictionary")]

    device = arguments.get("device", "")

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

    logger.info(f"Validating IP configuration: {ip_core}, params={parameters}, device={device}")

    # Validation results
    validation_results = {
        "valid": [],
        "warnings": [],
        "errors": [],
        "info": []
    }

    # Build comprehensive search query for ALL parameters
    param_search_terms = " ".join([f"{k} {v}" for k, v in parameters.items()])
    query_text = f"{ip_core} configuration {param_search_terms}"

    if device:
        query_text += f" {device} device compatibility"

    query_text += " valid range specifications requirements limitations"

    # Execute broad search to get relevant documentation
    search_query = SearchQuery(query=query_text, top_k=10)
    results = embedder.vector_store.search(search_query)

    if not results:
        validation_results["warnings"].append({
            "message": f"No documentation found for {ip_core}. Cannot validate parameters.",
            "severity": "HIGH",
            "doc_ref": "N/A"
        })
    else:
        # Analyze results for parameter validation
        # Extract all result text for analysis
        doc_text = "\n".join([r.snippet or r.text or "" for r in results[:5]])
        doc_text_lower = doc_text.lower()

        # Validate each parameter against documentation
        for param_name, param_value in parameters.items():
            param_name_lower = param_name.lower()
            param_value_str = str(param_value).lower()

            # Search for this specific parameter in results
            param_found = param_name_lower in doc_text_lower or param_value_str in doc_text_lower

            if param_found:
                # Check for specific validation keywords near the parameter
                param_context = _extract_context_around_keyword(doc_text_lower, param_value_str)

                # Look for warning indicators
                if any(word in param_context for word in ["warning", "caution", "note", "limitation", "max", "maximum", "min", "minimum"]):
                    # Find which document this came from
                    doc_ref = _find_doc_reference(results, param_value_str)

                    validation_results["warnings"].append({
                        "parameter": param_name,
                        "value": param_value,
                        "message": f"Parameter '{param_name}={param_value}' found in documentation with notes/limitations. Review documentation for constraints.",
                        "doc_ref": doc_ref,
                        "context": param_context[:200]
                    })
                else:
                    # Parameter mentioned positively
                    validation_results["valid"].append({
                        "parameter": param_name,
                        "value": param_value,
                        "message": f"Parameter '{param_name}={param_value}' found in documentation."
                    })
            else:
                # Parameter not explicitly mentioned - could be invalid or just not in search results
                validation_results["info"].append({
                    "parameter": param_name,
                    "value": param_value,
                    "message": f"Parameter '{param_name}={param_value}' not explicitly found in top documentation results. "
                             f"This may be valid but unusual, or may need different search terms."
                })

        # Device-specific validation
        if device:
            device_lower = device.lower()
            device_found = device_lower in doc_text_lower

            if not device_found:
                validation_results["warnings"].append({
                    "message": f"Device '{device}' not mentioned in documentation for {ip_core}. Verify device compatibility.",
                    "severity": "MEDIUM",
                    "doc_ref": "N/A"
                })

    # Format validation report
    report_lines = [
        f"# IP Configuration Validation: {ip_core}\n",
    ]

    if device:
        report_lines.append(f"**Target Device:** {device}\n")

    report_lines.append(f"**Parameters to Validate:** {len(parameters)}\n")

    # Summary counts
    num_valid = len(validation_results["valid"])
    num_warnings = len(validation_results["warnings"])
    num_errors = len(validation_results["errors"])
    num_info = len(validation_results["info"])

    report_lines.append("\n## Validation Summary\n")
    report_lines.append(f"- ✅ Valid: {num_valid}")
    report_lines.append(f"- ⚠️  Warnings: {num_warnings}")
    report_lines.append(f"- ❌ Errors: {num_errors}")
    report_lines.append(f"- ℹ️  Informational: {num_info}\n")

    # Errors first (blocking issues)
    if validation_results["errors"]:
        report_lines.append("\n## ❌ Errors (Must Fix)\n")
        for error in validation_results["errors"]:
            param_info = f"{error.get('parameter', 'N/A')}={error.get('value', 'N/A')}" if 'parameter' in error else ""
            report_lines.append(f"**Error:** {error['message']}")
            if param_info:
                report_lines.append(f"  - Parameter: `{param_info}`")
            if 'doc_ref' in error:
                report_lines.append(f"  - See: {error['doc_ref']}")
            if 'context' in error:
                report_lines.append(f"  - Context: {error['context'][:150]}...")
            report_lines.append("")

    # Warnings (should review)
    if validation_results["warnings"]:
        report_lines.append("\n## ⚠️  Warnings (Review Recommended)\n")
        for warning in validation_results["warnings"]:
            param_info = f"{warning.get('parameter', 'N/A')}={warning.get('value', 'N/A')}" if 'parameter' in warning else ""
            severity = warning.get('severity', 'MEDIUM')
            report_lines.append(f"**Warning [{severity}]:** {warning['message']}")
            if param_info:
                report_lines.append(f"  - Parameter: `{param_info}`")
            if 'doc_ref' in warning:
                report_lines.append(f"  - See: {warning['doc_ref']}")
            if 'context' in warning:
                report_lines.append(f"  - Context: {warning['context'][:150]}...")
            report_lines.append("")

    # Info (FYI)
    if validation_results["info"]:
        report_lines.append("\n## ℹ️  Informational\n")
        for info in validation_results["info"]:
            param_info = f"{info.get('parameter', 'N/A')}={info.get('value', 'N/A')}" if 'parameter' in info else ""
            report_lines.append(f"- {info['message']}")
            if param_info and 'parameter' in info:
                report_lines.append(f"  - Parameter: `{param_info}`")
            report_lines.append("")

    # Valid parameters
    if validation_results["valid"]:
        report_lines.append("\n## ✅ Valid Parameters\n")
        for valid in validation_results["valid"]:
            report_lines.append(f"- `{valid['parameter']}={valid['value']}`: {valid['message']}")

    # Add relevant documentation sections
    report_lines.append("\n## Referenced Documentation\n")
    for idx, result in enumerate(results[:5], start=1):
        title = result.title or "Unknown Document"
        page = result.slide_or_page or "?"
        report_lines.append(f"{idx}. **{title}** (Page {page})")

    # Recommendations
    report_lines.extend([
        "\n## Recommendations for TCL Generation",
    ])

    if validation_results["errors"]:
        report_lines.append("- ❌ **DO NOT PROCEED** - Fix errors before generating TCL")
    elif validation_results["warnings"]:
        report_lines.append("- ⚠️  **REVIEW WARNINGS** - Configuration may work but review recommended")
        report_lines.append("- Consider testing with safe default values first")
    else:
        report_lines.append("- ✅ **PROCEED** - No blocking issues found in documentation")

    report_lines.append("- Validate generated TCL against Libero constraints checker")
    report_lines.append("- Run timing analysis after synthesis to verify parameters")

    response = "\n".join(report_lines)
    return [TextContent(type="text", text=response)]


def _extract_context_around_keyword(text: str, keyword: str, context_chars: int = 200) -> str:
    """Extract text context around a keyword.

    Args:
        text: Full text to search
        keyword: Keyword to find
        context_chars: Characters of context before/after (default: 200)

    Returns:
        Context string or empty if keyword not found
    """
    idx = text.find(keyword)
    if idx == -1:
        return ""

    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(keyword) + context_chars)

    return text[start:end]


def _find_doc_reference(results: List[Any], keyword: str) -> str:
    """Find which document contains a keyword.

    Args:
        results: List of search results
        keyword: Keyword to search for

    Returns:
        Document reference string (title + page)
    """
    for result in results:
        snippet = (result.snippet or result.text or "").lower()
        if keyword in snippet:
            title = result.title or "Unknown"
            page = result.slide_or_page or "?"
            return f"{title} (Page {page})"

    return "Documentation (page unknown)"


async def handle_get_ip_dependencies(arguments: dict) -> List[TextContent]:
    """Handle get_ip_dependencies tool call.

    Identifies required IP cores, clocks, interfaces, and constraints for a given IP.
    Critical for system planning to prevent incomplete designs.

    Args:
        arguments: ip_core (required), use_case (optional)

    Returns:
        List of content blocks with dependency information
    """
    # Validate arguments
    ip_core = arguments.get("ip_core", "")
    if not ip_core or not ip_core.strip():
        return [TextContent(type="text", text="Error: 'ip_core' parameter is required")]

    use_case = arguments.get("use_case", "")

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

    logger.info(f"Analyzing dependencies for: {ip_core}, use_case={use_case}")

    # Build search queries for different dependency types
    queries = {
        "required_ips": f"{ip_core} required IP cores companion modules dependencies integration",
        "clocks": f"{ip_core} clock requirements frequency CCC PLL clock domains",
        "interfaces": f"{ip_core} interface AXI APB AMBA bus connections data path",
        "pins": f"{ip_core} pin count I/O requirements package pinout",
        "constraints": f"{ip_core} timing constraints SDC PDC requirements"
    }

    if use_case:
        for key in queries:
            queries[key] += f" {use_case}"

    # Execute searches for each dependency type
    dependency_info = {}
    for dep_type, query_text in queries.items():
        search_query = SearchQuery(query=query_text, top_k=5)
        results = embedder.vector_store.search(search_query)
        dependency_info[dep_type] = results

    # Analyze results to extract structured information
    report_lines = [
        f"# IP Dependencies Analysis: {ip_core}\n",
    ]

    if use_case:
        report_lines.append(f"**Use Case:** {use_case}\n")

    report_lines.append("This analysis identifies required components, clocks, interfaces, and constraints.\n")
    report_lines.append("---\n")

    # Required IP Cores
    report_lines.append("\n## Required / Companion IP Cores\n")
    required_results = dependency_info.get("required_ips", [])
    if required_results:
        # Extract mentions of other IP cores from results
        doc_text = "\n".join([r.snippet or r.text or "" for r in required_results[:3]])
        doc_text_lower = doc_text.lower()

        # Common IP dependencies
        common_deps = {
            "CCC": ["ccc", "clock conditioning", "pll"],
            "Interconnect": ["axi interconnect", "ahb", "apb bridge", "fabric"],
            "DMA": ["dma", "direct memory access"],
            "Reset": ["reset controller", "sysreset"],
            "MI-V": ["mi-v", "risc-v", "processor"]
        }

        found_deps = []
        for dep_name, keywords in common_deps.items():
            if any(kw in doc_text_lower for kw in keywords):
                found_deps.append(dep_name)

        if found_deps:
            report_lines.append(f"**Identified Dependencies:**\n")
            for dep in found_deps:
                report_lines.append(f"- {dep}")
            report_lines.append("")

        report_lines.append("\n**Documentation References:**\n")
        for idx, result in enumerate(required_results[:3], start=1):
            title = result.title or "Unknown Document"
            page = result.slide_or_page or "?"
            snippet = result.snippet or result.text or ""
            report_lines.append(f"{idx}. **{title}** (Page {page})")
            if snippet:
                snippet_short = snippet[:200] + "..." if len(snippet) > 200 else snippet
                report_lines.append(f"   > {snippet_short}\n")
    else:
        report_lines.append("*No specific dependency information found. Check documentation manually.*\n")

    # Clock Requirements
    report_lines.append("\n## Clock Requirements\n")
    clock_results = dependency_info.get("clocks", [])
    if clock_results:
        report_lines.append("**Clock Information Found:**\n")
        for idx, result in enumerate(clock_results[:3], start=1):
            title = result.title or "Unknown Document"
            page = result.slide_or_page or "?"
            snippet = result.snippet or result.text or ""

            report_lines.append(f"{idx}. **{title}** (Page {page})")
            if snippet:
                # Look for frequency mentions
                import re
                freq_mentions = re.findall(r'\d+\s*[MG]Hz', snippet, re.IGNORECASE)
                if freq_mentions:
                    report_lines.append(f"   - Frequencies mentioned: {', '.join(freq_mentions[:5])}")

                snippet_short = snippet[:200] + "..." if len(snippet) > 200 else snippet
                report_lines.append(f"   > {snippet_short}\n")
    else:
        report_lines.append("*Check IP core documentation for clock requirements.*\n")

    # Interface Requirements
    report_lines.append("\n## Interface Requirements\n")
    interface_results = dependency_info.get("interfaces", [])
    if interface_results:
        doc_text = "\n".join([r.snippet or r.text or "" for r in interface_results[:3]])
        doc_text_lower = doc_text.lower()

        # Detect interface types
        interfaces_found = []
        if "axi" in doc_text_lower or "axi4" in doc_text_lower:
            interfaces_found.append("AXI4 (Advanced eXtensible Interface)")
        if "apb" in doc_text_lower:
            interfaces_found.append("APB (Advanced Peripheral Bus)")
        if "ahb" in doc_text_lower:
            interfaces_found.append("AHB (Advanced High-performance Bus)")
        if "fabric" in doc_text_lower:
            interfaces_found.append("FPGA Fabric")

        if interfaces_found:
            report_lines.append("**Interfaces Detected:**\n")
            for iface in interfaces_found:
                report_lines.append(f"- {iface}")
            report_lines.append("")

        report_lines.append("\n**Documentation References:**\n")
        for idx, result in enumerate(interface_results[:2], start=1):
            title = result.title or "Unknown Document"
            page = result.slide_or_page or "?"
            report_lines.append(f"{idx}. {title} (Page {page})")
    else:
        report_lines.append("*Review IP core documentation for interface specifications.*\n")

    # Pin Requirements
    report_lines.append("\n## Pin Requirements\n")
    pin_results = dependency_info.get("pins", [])
    if pin_results:
        doc_text = "\n".join([r.snippet or r.text or "" for r in pin_results[:2]])

        # Try to extract pin counts
        import re
        pin_numbers = re.findall(r'(\d+)\s*pins?', doc_text, re.IGNORECASE)
        if pin_numbers:
            report_lines.append(f"**Pin Counts Mentioned:** {', '.join(pin_numbers[:5])} pins\n")

        report_lines.append("**Documentation References:**\n")
        for idx, result in enumerate(pin_results[:2], start=1):
            title = result.title or "Unknown Document"
            page = result.slide_or_page or "?"
            report_lines.append(f"{idx}. {title} (Page {page})")
    else:
        report_lines.append("*Check board design guide for pin requirements.*\n")

    # Constraint Requirements
    report_lines.append("\n## Timing Constraints Requirements\n")
    constraint_results = dependency_info.get("constraints", [])
    if constraint_results:
        report_lines.append("**Constraint Documentation Found:**\n")
        for idx, result in enumerate(constraint_results[:2], start=1):
            title = result.title or "Unknown Document"
            page = result.slide_or_page or "?"
            report_lines.append(f"{idx}. {title} (Page {page})")
        report_lines.append("\n*Use `get_timing_constraints` tool for specific constraint examples.*\n")
    else:
        report_lines.append("*Timing constraints may be required. Check documentation.*\n")

    # System Integration Recommendations
    report_lines.extend([
        "\n## System Integration Checklist\n",
        "Use this checklist when integrating this IP into your design:\n",
        "- [ ] Verify all required companion IP cores are included",
        "- [ ] Configure clock sources (add PF_CCC if needed)",
        "- [ ] Connect interfaces (AXI/APB interconnects)",
        "- [ ] Allocate sufficient pins (check device package)",
        "- [ ] Add timing constraints (SDC/PDC files)",
        "- [ ] Verify device compatibility and resources",
        "\n## Next Steps for tcl_monster Integration\n",
        "1. Use `query_ip_parameters` to get configuration options for each IP",
        "2. Use `validate_ip_configuration` to pre-check parameters",
        "3. Generate TCL scripts for all required components",
        "4. Use `get_timing_constraints` to create constraint files",
    ])

    response = "\n".join(report_lines)
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
