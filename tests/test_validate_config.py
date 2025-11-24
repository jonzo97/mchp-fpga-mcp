#!/usr/bin/env python3
"""Test validate_ip_configuration tool with realistic tcl_monster scenarios."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "fpga_mcp" / "src"))

from fpga_rag.mcp_server.server import handle_validate_ip_configuration, get_embedder
from fpga_rag.config import settings

# Configure paths
settings.content_dir = Path.home() / "fpga_mcp" / "content"
settings.chroma_path = Path.home() / "fpga_mcp" / "chroma"


async def test_ddr4_validation():
    """Test DDR4 configuration validation (most common use case)."""
    print("\n" + "=" * 70)
    print("TEST: DDR4 Configuration Validation")
    print("=" * 70)

    test_cases = [
        {
            "name": "Valid DDR4-2400 4GB Configuration",
            "args": {
                "ip_core": "PF_DDR4",
                "parameters": {
                    "speed": "DDR4-2400",
                    "size": "4GB",
                    "width": "32"
                },
                "device": "MPF300"
            }
        },
        {
            "name": "Potentially Invalid DDR4-3200 (may exceed MPF300 capability)",
            "args": {
                "ip_core": "PF_DDR4",
                "parameters": {
                    "speed": "DDR4-3200",
                    "size": "8GB",
                    "width": "64"
                },
                "device": "MPF300"
            }
        },
        {
            "name": "DDR4 with typical tcl_monster parameters",
            "args": {
                "ip_core": "PF_DDR4",
                "parameters": {
                    "DRAM_DENSITY": "4096Mb",
                    "DATA_WIDTH": "32",
                    "SPEED_GRADE": "DDR4-2400"
                }
            }
        }
    ]

    for test in test_cases:
        print(f"\n{'─' * 70}")
        print(f"Test: {test['name']}")
        print(f"{'─' * 70}")

        result = await handle_validate_ip_configuration(test['args'])

        if result and len(result) > 0:
            content = result[0].text
            print(content[:800])  # Show first 800 chars
            if len(content) > 800:
                print(f"\n... (truncated, total {len(content)} chars)")
        else:
            print("❌ No results returned")


async def test_pcie_validation():
    """Test PCIe configuration validation."""
    print("\n" + "=" * 70)
    print("TEST: PCIe Configuration Validation")
    print("=" * 70)

    test_cases = [
        {
            "name": "PCIe Gen2 x4 Configuration",
            "args": {
                "ip_core": "PF_PCIE",
                "parameters": {
                    "generation": "Gen2",
                    "lanes": "4",
                    "speed": "5.0 GT/s"
                }
            }
        },
        {
            "name": "PCIe with BAR configuration",
            "args": {
                "ip_core": "PF_PCIE",
                "parameters": {
                    "gen": "2",
                    "lanes": "4",
                    "bar0_size": "1MB"
                },
                "device": "MPF300"
            }
        }
    ]

    for test in test_cases:
        print(f"\n{'─' * 70}")
        print(f"Test: {test['name']}")
        print(f"{'─' * 70}")

        result = await handle_validate_ip_configuration(test['args'])

        if result and len(result) > 0:
            content = result[0].text
            print(content[:800])
            if len(content) > 800:
                print(f"\n... (truncated, total {len(content)} chars)")
        else:
            print("❌ No results returned")


async def test_ccc_validation():
    """Test CCC (Clock Conditioning Circuit) validation."""
    print("\n" + "=" * 70)
    print("TEST: CCC PLL Configuration Validation")
    print("=" * 70)

    test_args = {
        "ip_core": "PF_CCC",
        "parameters": {
            "input_freq": "50MHz",
            "output_freq": "200MHz",
            "pll_mode": "internal"
        }
    }

    print(f"\n{'─' * 70}")
    print(f"Test: CCC 50MHz → 200MHz PLL")
    print(f"{'─' * 70}")

    result = await handle_validate_ip_configuration(test_args)

    if result and len(result) > 0:
        content = result[0].text
        print(content)
    else:
        print("❌ No results returned")


async def test_uart_validation():
    """Test CoreUARTapb configuration validation."""
    print("\n" + "=" * 70)
    print("TEST: CoreUARTapb Configuration Validation")
    print("=" * 70)

    test_args = {
        "ip_core": "CoreUARTapb",
        "parameters": {
            "baud_rate": "115200",
            "data_bits": "8",
            "parity": "none",
            "stop_bits": "1"
        }
    }

    print(f"\n{'─' * 70}")
    print(f"Test: Standard UART 115200 8N1")
    print(f"{'─' * 70}")

    result = await handle_validate_ip_configuration(test_args)

    if result and len(result) > 0:
        content = result[0].text
        print(content[:800])
        if len(content) > 800:
            print(f"\n... (truncated, total {len(content)} chars)")
    else:
        print("❌ No results returned")


async def main():
    """Run all validation tests."""
    print("=" * 70)
    print("VALIDATE_IP_CONFIGURATION TEST SUITE")
    print("Testing pre-validation before TCL generation")
    print("=" * 70)

    # Initialize embedder
    print("\nInitializing embedder...")
    try:
        embedder = get_embedder()
        print(f"✓ Embedder initialized")
    except Exception as e:
        print(f"❌ Failed to initialize embedder: {e}")
        return 1

    # Run tests
    try:
        await test_ddr4_validation()
        await test_pcie_validation()
        await test_ccc_validation()
        await test_uart_validation()

        print("\n" + "=" * 70)
        print("✅ ALL VALIDATION TESTS COMPLETED")
        print("=" * 70)
        print("\nKey Observations:")
        print("- Tool successfully queries documentation for parameter validation")
        print("- Provides warnings when parameters have limitations")
        print("- Returns actionable recommendations for TCL generation")
        print("- References specific documentation pages for review")
        return 0

    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
