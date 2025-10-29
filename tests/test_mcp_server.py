#!/usr/bin/env python3
"""Tests for FPGA MCP server.

Tests cover:
- Tool listing
- Search functionality
- Document info
- Error handling
- Rich content formatting
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add fpga_mcp to path
FPGA_MCP_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(FPGA_MCP_PATH))


class TestMCPServerTools:
    """Test MCP server tool definitions."""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test that list_tools returns expected tools."""
        from fpga_rag.mcp_server.server import list_tools

        tools = await list_tools()

        assert len(tools) >= 2, "Should have at least 2 tools"

        tool_names = [tool.name for tool in tools]
        assert "search_fpga_docs" in tool_names
        assert "get_fpga_doc_info" in tool_names

    @pytest.mark.asyncio
    async def test_search_tool_schema(self):
        """Test search tool has correct schema."""
        from fpga_rag.mcp_server.server import list_tools

        tools = await list_tools()
        search_tool = next(t for t in tools if t.name == "search_fpga_docs")

        # Check required parameters
        assert "query" in search_tool.inputSchema["properties"]
        assert "query" in search_tool.inputSchema["required"]

        # Check optional parameters
        assert "top_k" in search_tool.inputSchema["properties"]
        assert "document_type" in search_tool.inputSchema["properties"]

        # Check constraints
        top_k_schema = search_tool.inputSchema["properties"]["top_k"]
        assert top_k_schema.get("minimum") == 1
        assert top_k_schema.get("maximum") == 20


class TestSearchTool:
    """Test search_fpga_docs tool functionality."""

    @pytest.fixture
    def mock_embedder(self):
        """Create a mock DocumentEmbedder."""
        embedder = Mock()
        embedder.vector_store = Mock()
        embedder.vector_store.is_available.return_value = True

        # Mock search results
        result = Mock()
        result.title = "PolarFire FPGA Datasheet"
        result.slide_or_page = 42
        result.score = 0.85
        result.snippet = "DDR4 memory controller supports up to 1600 MHz..."
        result.text = result.snippet
        result.section = "Memory Controller"
        result.metadata = {}

        embedder.vector_store.search.return_value = [result]

        return embedder

    @pytest.mark.asyncio
    async def test_search_valid_query(self, mock_embedder):
        """Test search with valid query returns results."""
        from fpga_rag.mcp_server.server import handle_search_tool

        with patch('fpga_rag.mcp_server.server.get_embedder', return_value=mock_embedder):
            arguments = {
                "query": "DDR4 configuration",
                "top_k": 5
            }

            results = await handle_search_tool(arguments)

            assert len(results) > 0
            assert results[0].type == "text"
            assert "DDR4" in results[0].text or "PolarFire" in results[0].text

    @pytest.mark.asyncio
    async def test_search_empty_query(self, mock_embedder):
        """Test search with empty query returns error."""
        from fpga_rag.mcp_server.server import handle_search_tool

        with patch('fpga_rag.mcp_server.server.get_embedder', return_value=mock_embedder):
            arguments = {
                "query": "",
                "top_k": 5
            }

            results = await handle_search_tool(arguments)

            assert len(results) == 1
            assert "error" in results[0].text.lower() or "required" in results[0].text.lower()

    @pytest.mark.asyncio
    async def test_search_invalid_top_k(self, mock_embedder):
        """Test search with invalid top_k returns error."""
        from fpga_rag.mcp_server.server import handle_search_tool

        with patch('fpga_rag.mcp_server.server.get_embedder', return_value=mock_embedder):
            arguments = {
                "query": "DDR4",
                "top_k": 100  # Exceeds max of 20
            }

            results = await handle_search_tool(arguments)

            assert len(results) == 1
            assert "error" in results[0].text.lower()

    @pytest.mark.asyncio
    async def test_search_vector_store_unavailable(self):
        """Test search when vector store is not available."""
        from fpga_rag.mcp_server.server import handle_search_tool

        mock_embedder = Mock()
        mock_embedder.vector_store = Mock()
        mock_embedder.vector_store.is_available.return_value = False

        with patch('fpga_rag.mcp_server.server.get_embedder', return_value=mock_embedder):
            arguments = {
                "query": "DDR4",
                "top_k": 5
            }

            results = await handle_search_tool(arguments)

            assert len(results) == 1
            assert "not available" in results[0].text.lower()

    @pytest.mark.asyncio
    async def test_search_no_results(self, mock_embedder):
        """Test search when no results are found."""
        from fpga_rag.mcp_server.server import handle_search_tool

        # Mock empty search results
        mock_embedder.vector_store.search.return_value = []

        with patch('fpga_rag.mcp_server.server.get_embedder', return_value=mock_embedder):
            arguments = {
                "query": "nonexistent query",
                "top_k": 5
            }

            results = await handle_search_tool(arguments)

            assert len(results) == 1
            assert "no results found" in results[0].text.lower()


class TestDocInfoTool:
    """Test get_fpga_doc_info tool functionality."""

    @pytest.fixture
    def mock_embedder_with_docs(self):
        """Create a mock DocumentEmbedder with document info."""
        embedder = Mock()
        embedder.vector_store = Mock()
        embedder.vector_store.is_available.return_value = True

        # Mock collection info
        embedder.vector_store.get_collection_info.return_value = {
            'name': 'fpga_docs',
            'points_count': 1234,
            'path': '/home/user/fpga_mcp/chroma'
        }

        # Mock collection.get for catalog
        embedder.vector_store.collection = Mock()
        embedder.vector_store.collection.get.return_value = {
            'metadatas': [
                {'doc_id': 'PolarFire_Datasheet', 'title': 'PolarFire FPGA Datasheet', 'slide_or_page': 1},
                {'doc_id': 'PolarFire_Datasheet', 'title': 'PolarFire FPGA Datasheet', 'slide_or_page': 2},
                {'doc_id': 'Memory_Controller', 'title': 'Memory Controller Guide', 'slide_or_page': 1},
            ]
        }

        return embedder

    @pytest.mark.asyncio
    async def test_doc_info_returns_catalog(self, mock_embedder_with_docs):
        """Test doc info returns document catalog."""
        from fpga_rag.mcp_server.server import handle_doc_info_tool

        with patch('fpga_rag.mcp_server.server.get_embedder', return_value=mock_embedder_with_docs):
            arguments = {}

            results = await handle_doc_info_tool(arguments)

            assert len(results) == 1
            assert results[0].type == "text"
            assert "1,234" in results[0].text or "1234" in results[0].text  # Total chunks
            assert "2" in results[0].text  # Document count

    @pytest.mark.asyncio
    async def test_doc_info_vector_store_unavailable(self):
        """Test doc info when vector store is unavailable."""
        from fpga_rag.mcp_server.server import handle_doc_info_tool

        mock_embedder = Mock()
        mock_embedder.vector_store = Mock()
        mock_embedder.vector_store.is_available.return_value = False

        with patch('fpga_rag.mcp_server.server.get_embedder', return_value=mock_embedder):
            arguments = {}

            results = await handle_doc_info_tool(arguments)

            assert len(results) == 1
            assert "not available" in results[0].text.lower()


class TestDynamicDocumentCatalog:
    """Test dynamic document catalog generation."""

    def test_catalog_generates_correctly(self):
        """Test that catalog extracts unique documents correctly."""
        from fpga_rag.mcp_server.server import get_dynamic_document_catalog

        mock_embedder = Mock()
        mock_embedder.vector_store = Mock()
        mock_embedder.vector_store.is_available.return_value = True

        # Mock metadata from ChromaDB
        mock_embedder.vector_store.collection = Mock()
        mock_embedder.vector_store.collection.get.return_value = {
            'metadatas': [
                {'doc_id': 'doc1', 'title': 'Document 1', 'slide_or_page': 1},
                {'doc_id': 'doc1', 'title': 'Document 1', 'slide_or_page': 2},
                {'doc_id': 'doc1', 'title': 'Document 1', 'slide_or_page': 3},
                {'doc_id': 'doc2', 'title': 'Document 2', 'slide_or_page': 1},
                {'doc_id': 'doc2', 'title': 'Document 2', 'slide_or_page': 2},
            ]
        }

        with patch('fpga_rag.mcp_server.server.get_embedder', return_value=mock_embedder):
            catalog = get_dynamic_document_catalog()

            assert len(catalog) == 2
            assert catalog[0]['doc_id'] in ['doc1', 'doc2']
            assert catalog[0]['page_count'] in [2, 3]


class TestUtilityFunctions:
    """Test utility functions for content formatting."""

    def test_csv_to_markdown_basic(self, tmp_path):
        """Test CSV to Markdown conversion."""
        from fpga_rag.mcp_server.server import read_csv_as_markdown

        # Create test CSV
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Header1,Header2\\nValue1,Value2\\nValue3,Value4\\n")

        result = read_csv_as_markdown(csv_file)

        assert "Header1" in result
        assert "Header2" in result
        assert "---" in result  # Markdown table separator
        assert "Value1" in result

    def test_csv_to_markdown_nonexistent(self):
        """Test CSV to Markdown with nonexistent file."""
        from fpga_rag.mcp_server.server import read_csv_as_markdown

        result = read_csv_as_markdown("/nonexistent/file.csv")

        assert "not found" in result.lower()

    def test_image_encoding(self, tmp_path):
        """Test base64 image encoding."""
        from fpga_rag.mcp_server.server import encode_image_base64

        # Create tiny test image (1x1 PNG)
        png_data = b'\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x01\\x08\\x02\\x00\\x00\\x00\\x90wS\\xde'
        image_file = tmp_path / "test.png"
        image_file.write_bytes(png_data)

        result = encode_image_base64(image_file)

        assert len(result) > 0
        assert result.startswith("iVBOR")  # PNG header in base64

    def test_image_encoding_nonexistent(self):
        """Test base64 encoding with nonexistent image."""
        from fpga_rag.mcp_server.server import encode_image_base64

        result = encode_image_base64("/nonexistent/image.png")

        assert result == ""


class TestResultFormatting:
    """Test search result formatting."""

    def test_format_search_results_basic(self):
        """Test basic result formatting."""
        from fpga_rag.mcp_server.server import format_search_results_rich

        # Create mock results
        result = Mock()
        result.title = "Test Document"
        result.slide_or_page = 10
        result.score = 0.95
        result.snippet = "Test snippet content"
        result.text = "Test snippet content"
        result.section = "Test Section"
        result.metadata = {}

        results = format_search_results_rich([result], "test query")

        assert len(results) > 0
        assert results[0].type == "text"
        assert "Test Document" in results[0].text
        assert "test query" in results[0].text.lower()

    def test_format_truncates_long_snippets(self):
        """Test that long snippets are truncated."""
        from fpga_rag.mcp_server.server import format_search_results_rich

        # Create mock result with long snippet
        result = Mock()
        result.title = "Test Document"
        result.slide_or_page = 10
        result.score = 0.95
        result.snippet = "x" * 1000  # Very long snippet
        result.text = result.snippet
        result.section = ""
        result.metadata = {}

        results = format_search_results_rich([result], "test")

        assert len(results) > 0
        # Should be truncated to ~500 chars
        assert "..." in results[0].text


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
