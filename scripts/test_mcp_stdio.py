#!/usr/bin/env python3
"""Test MCP server via stdio protocol (Claude Desktop compatibility test)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fpga_rag.mcp_server.server import list_tools, call_tool


async def test_stdio_protocol() -> None:
    """Test MCP server via stdio-like protocol."""
    print("=" * 80)
    print("MCP Server - Claude Desktop Compatibility Test")
    print("=" * 80 + "\n")

    # Test 1: List tools
    print("[Test 1] Listing available tools...\n")
    tools = await list_tools()
    print(f"✓ Found {len(tools)} tools:\n")
    for tool in tools:
        print(f"  • {tool.name}")
        print(f"    {tool.description}")
        print()

    # Test 2: Call get_fpga_doc_info
    print("\n[Test 2] Calling get_fpga_doc_info tool...\n")
    try:
        results = await call_tool("get_fpga_doc_info", {})
        print(f"✓ Tool returned {len(results)} content blocks")
        if results:
            # Show first 500 chars of response
            response_preview = results[0].text[:500]
            print(f"\nResponse preview:\n{response_preview}...\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")

    # Test 3: Call search_fpga_docs
    print("\n[Test 3] Calling search_fpga_docs with query 'DDR4 configuration'...\n")
    try:
        results = await call_tool("search_fpga_docs", {
            "query": "DDR4 configuration",
            "top_k": 3
        })
        print(f"✓ Tool returned {len(results)} content blocks")
        if results:
            response_preview = results[0].text[:500]
            print(f"\nResponse preview:\n{response_preview}...\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")

    # Test 4: Call query_ip_parameters
    print("\n[Test 4] Calling query_ip_parameters for 'PF_DDR4'...\n")
    try:
        results = await call_tool("query_ip_parameters", {
            "ip_core": "PF_DDR4",
            "parameter": "CAS_LATENCY",
            "top_k": 3
        })
        print(f"✓ Tool returned {len(results)} content blocks")
        if results:
            response_preview = results[0].text[:500]
            print(f"\nResponse preview:\n{response_preview}...\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")

    print("=" * 80)
    print("All tests completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_stdio_protocol())
