#!/usr/bin/env python3
"""Manual testing script for MCP tools.

Tests the tcl_monster-specific tools with real queries:
- query_ip_parameters
- explain_error
- get_timing_constraints
"""
import asyncio
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path.home() / "fpga_mcp" / "src"))

from fpga_rag.mcp_server.server import (
    handle_query_ip_parameters,
    handle_explain_error,
    handle_get_timing_constraints,
    get_embedder
)
from fpga_rag.config import settings

# Configure paths
settings.content_dir = Path.home() / "fpga_mcp" / "content"
settings.chroma_path = Path.home() / "fpga_mcp" / "chroma"


async def test_query_ip_parameters():
    """Test IP parameter queries for DDR4, PCIe, CCC."""
    print("\n" + "=" * 70)
    print("TEST 1: query_ip_parameters")
    print("=" * 70)

    test_cases = [
        {
            "name": "DDR4 Memory Size",
            "args": {"ip_core": "PF_DDR4", "parameter": "memory size", "top_k": 3}
        },
        {
            "name": "DDR4 Speed Grade",
            "args": {"ip_core": "PF_DDR4", "parameter": "speed grade DDR4-2400", "top_k": 3}
        },
        {
            "name": "PCIe Lane Configuration",
            "args": {"ip_core": "PF_PCIE", "parameter": "lane configuration x4", "top_k": 3}
        },
        {
            "name": "CCC PLL Configuration",
            "args": {"ip_core": "PF_CCC", "parameter": "PLL multiplier divider", "top_k": 3}
        },
        {
            "name": "CoreUARTapb Baud Rate",
            "args": {"ip_core": "CoreUARTapb", "parameter": "baud rate", "top_k": 3}
        }
    ]

    for test in test_cases:
        print(f"\n{'─' * 70}")
        print(f"Test: {test['name']}")
        print(f"Args: {test['args']}")
        print(f"{'─' * 70}")

        result = await handle_query_ip_parameters(test['args'])

        if result and len(result) > 0:
            content = result[0].text
            # Show first 500 chars of result
            print(content[:500])
            if len(content) > 500:
                print(f"\n... (truncated, total {len(content)} chars)")
        else:
            print("❌ No results returned")


async def test_explain_error():
    """Test error explanation with real Libero error messages."""
    print("\n" + "=" * 70)
    print("TEST 2: explain_error")
    print("=" * 70)

    test_cases = [
        {
            "name": "Timing Violation",
            "args": {
                "error_message": "Critical Warning: Timing constraint not met on path CLK to DATA",
                "context": "DDR4 memory controller",
                "top_k": 3
            }
        },
        {
            "name": "Clock Domain Crossing",
            "args": {
                "error_message": "Clock domain CDC violation detected",
                "context": "PCIe to fabric interface",
                "top_k": 3
            }
        },
        {
            "name": "Resource Constraint",
            "args": {
                "error_message": "Error: Insufficient PLL resources for clock configuration",
                "top_k": 3
            }
        },
        {
            "name": "Pin Assignment",
            "args": {
                "error_message": "Error: Pin constraint violation - incompatible I/O standard",
                "top_k": 3
            }
        }
    ]

    for test in test_cases:
        print(f"\n{'─' * 70}")
        print(f"Test: {test['name']}")
        print(f"Error: {test['args']['error_message']}")
        print(f"{'─' * 70}")

        result = await handle_explain_error(test['args'])

        if result and len(result) > 0:
            content = result[0].text
            # Show first 500 chars of result
            print(content[:500])
            if len(content) > 500:
                print(f"\n... (truncated, total {len(content)} chars)")
        else:
            print("❌ No results returned")


async def test_get_timing_constraints():
    """Test timing constraint examples."""
    print("\n" + "=" * 70)
    print("TEST 3: get_timing_constraints")
    print("=" * 70)

    test_cases = [
        {
            "name": "Clock Definition for DDR4",
            "args": {
                "constraint_type": "clock definition",
                "ip_or_interface": "DDR4",
                "top_k": 3
            }
        },
        {
            "name": "Input Delay Constraint",
            "args": {
                "constraint_type": "input delay",
                "ip_or_interface": "PCIe",
                "top_k": 3
            }
        },
        {
            "name": "False Path for CDC",
            "args": {
                "constraint_type": "false path",
                "ip_or_interface": "clock domain crossing",
                "top_k": 3
            }
        },
        {
            "name": "Multi-cycle Path",
            "args": {
                "constraint_type": "multi-cycle path",
                "top_k": 3
            }
        }
    ]

    for test in test_cases:
        print(f"\n{'─' * 70}")
        print(f"Test: {test['name']}")
        print(f"Args: {test['args']}")
        print(f"{'─' * 70}")

        result = await handle_get_timing_constraints(test['args'])

        if result and len(result) > 0:
            content = result[0].text
            # Show first 500 chars of result
            print(content[:500])
            if len(content) > 500:
                print(f"\n... (truncated, total {len(content)} chars)")
        else:
            print("❌ No results returned")


async def main():
    """Run all tests."""
    print("=" * 70)
    print("MCP TOOLS MANUAL TEST SUITE")
    print("Testing tcl_monster-specific tools with real queries")
    print("=" * 70)

    # Initialize embedder
    print("\nInitializing embedder...")
    try:
        embedder = get_embedder()
        print(f"✓ Embedder initialized with {embedder.vector_store.get_collection_info().get('points_count', 0)} documents")
    except Exception as e:
        print(f"❌ Failed to initialize embedder: {e}")
        return 1

    # Run tests
    try:
        await test_query_ip_parameters()
        await test_explain_error()
        await test_get_timing_constraints()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 70)
        return 0

    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
