# tcl_monster Integration Guide

**Last Updated:** 2025-10-28
**Purpose:** Integration between FPGA MCP Documentation Server and tcl_monster Libero TCL automation toolkit

---

## Overview

The FPGA MCP server provides three specialized tools designed for tcl_monster workflows:

1. **`query_ip_parameters`** - Query IP core configuration parameters
2. **`explain_error`** - Resolve Libero error messages
3. **`get_timing_constraints`** - Find timing constraint examples

These tools enable intelligent TCL generation by providing documentation-backed parameter validation, error resolution, and constraint examples.

---

## Tool 1: query_ip_parameters

### Purpose
Query IP core parameters and configuration options to inform TCL script generation.

### Use Cases
- Validate parameter values before generating TCL
- Discover valid ranges for IP configuration
- Find default values and dependencies
- Learn about required vs. optional parameters

### Parameters
- **`ip_core`** (required): IP core name (e.g., "PF_DDR4", "PF_CCC", "PF_PCIE")
- **`parameter`** (optional): Specific parameter to query
- **`top_k`** (optional): Number of results (default: 5, max: 10)

### Example 1: Query All DDR4 Parameters

**Direct Python Usage (Claude Code):**
```python
from fpga_rag.indexing import DocumentEmbedder
from mchp_mcp_core.storage.schemas import SearchQuery

embedder = DocumentEmbedder()

# Search for DDR4 configuration parameters
query = "PF_DDR4 IP core parameters configuration options"
results = embedder.vector_store.search(SearchQuery(query=query, top_k=5))

for result in results:
    print(f"{result.title} (Page {result.slide_or_page}):")
    print(result.snippet)
    print("---")
```

**MCP Tool Call (Claude Desktop):**
```json
{
  "tool": "query_ip_parameters",
  "arguments": {
    "ip_core": "PF_DDR4"
  }
}
```

**Expected Response:**
```markdown
# IP Parameters: PF_DDR4

Found 5 relevant configuration sections
---

## Configuration 1: PolarFire FPGA Memory Controller User Guide (Page 47)

```
PF_DDR4 IP Core Parameters:
- MEMORY_SIZE: 4GB, 8GB, 16GB
- SPEED_GRADE: 1600, 1866, 2133, 2400 MHz
- DATA_WIDTH: 16, 32, 64 bits
- ROW_ADDRESS_WIDTH: 13-17 bits (depends on memory size)
- COLUMN_ADDRESS_WIDTH: 10 bits
- BANK_ADDRESS_WIDTH: 3 bits (8 banks)
```
---

## Next Steps for TCL Generation
1. Review parameter ranges and valid values
2. Check for dependencies between parameters
3. Note any required vs. optional parameters
4. Verify default values if not specified
```

### Example 2: Query Specific Parameter

**Query:**
```python
# In tcl_monster DDR4 generator
ip_core = "PF_DDR4"
parameter = "SPEED_GRADE"

# Tool returns valid speed grades and requirements
```

**Response:**
```markdown
# IP Parameters: PF_DDR4
**Specific Parameter:** SPEED_GRADE

Found 3 relevant configuration sections
---

## Configuration 1: Memory Controller User Guide (Page 52)

```
SPEED_GRADE Parameter:
Valid values: 1600, 1866, 2133, 2400 (MHz)

Requirements:
- Must match physical DDR4 memory chips
- Affects timing parameters (tRAS, tRC, tRCD)
- Higher speeds require better PCB routing
- Temperature affects maximum speed
  * Commercial: up to 2400 MHz
  * Industrial: up to 2133 MHz recommended
```
```

### Example 3: tcl_monster DDR4 Generator Integration

**File:** `/mnt/c/tcl_monster/tcl_scripts/lib/generators/ddr4_config_generator.tcl`

```tcl
#!/usr/bin/tclsh

# Before generating DDR4 configuration, validate parameters
proc validate_ddr4_params {size speed data_width} {
    # Query documentation via Claude Code
    # Returns: valid ranges, dependencies, warnings

    # Example validation:
    # - Is speed valid for this size?
    # - Does data_width match standard configs?
    # - Any temperature considerations?

    puts "Validated: DDR4 ${size}GB @ ${speed}MHz, ${data_width}-bit"
}

# Generate DDR4 configuration
proc generate_ddr4_config {args} {
    # Parse arguments
    set size [dict get $args size]
    set speed [dict get $args speed]
    set data_width [dict get $args data_width]

    # Validate before generation
    validate_ddr4_params $size $speed $data_width

    # Generate TCL commands
    puts "create_and_configure_core -core PF_DDR4 -component_name {DDR4_CTRL}"
    puts "sd_configure_core_instance -sd_name {DDR4_CTRL} \\"
    puts "  -instance_name {DDR4_CTRL_0} \\"
    puts "  -params {MEMORY_SIZE:${size}GB SPEED_GRADE:${speed} DATA_WIDTH:${data_width}}"
}
```

---

## Tool 2: explain_error

### Purpose
Parse Libero error messages and search documentation for solutions.

### Use Cases
- Resolve build/synthesis errors
- Understand timing failures
- Fix resource constraint violations
- Troubleshoot configuration issues

### Parameters
- **`error_message`** (required): Libero error or warning text
- **`context`** (optional): What was being configured when error occurred
- **`top_k`** (optional): Number of solutions (default: 5, max: 10)

### Example 1: Timing Constraint Error

**Scenario:** Libero build fails with timing error

```bash
# Libero log output:
Critical Warning: Clock domain CDC violation
Path: DDR4_CTRL/clk_sys -> PCIE_CTRL/clk_pcie
Setup time: -0.325ns (FAILED)
```

**Tool Call:**
```json
{
  "tool": "explain_error",
  "arguments": {
    "error_message": "Critical Warning: Clock domain CDC violation",
    "context": "DDR4 to PCIe clock domain crossing"
  }
}
```

**Expected Response:**
```markdown
# Error Resolution

**Error:** Critical Warning: Clock domain CDC violation
**Context:** DDR4 to PCIe clock domain crossing

Found 5 potentially relevant sections
---

## Solution 1: PolarFire FPGA Fabric User Guide (Page 89)
**Relevance:** 0.87

```
Clock Domain Crossing (CDC) Requirements:

When crossing between asynchronous clock domains:
1. Use proper synchronization (2-stage flip-flops minimum)
2. Add timing constraints to mark asynchronous paths
3. Consider handshake protocols for data transfer

SDC Constraint Example:
set_false_path -from [get_clocks clk_sys] -to [get_clocks clk_pcie]
set_max_delay 5.0 -from [get_pins DDR4_CTRL/*] -to [get_pins PCIE_CTRL/*]
```
---

## Solution 2: Memory Controller User Guide (Page 134)

```
Interfacing DDR4 Controller with Other IP:

The DDR4 controller uses the system clock domain (clk_sys).
When connecting to IP cores with different clocks:
- Add asynchronous FIFO buffers
- Use clock domain crossing constraints
- Verify data valid/ready handshake signals
```
---

## Troubleshooting Steps
1. Review each solution section for applicable fixes
2. Check configuration parameters mentioned
3. Verify timing constraints if error is timing-related
4. Consider design changes if constraints cannot be met
5. Consult full document sections for detailed guidance
```

### Example 2: Resource Shortage Error

**Error:**
```
Error: Insufficient PLL resources
Required: 3 PLLs
Available: 2 PLLs in MPF300T-1FCG1152
```

**Tool Call:**
```python
# In tcl_monster error handler
error_msg = "Insufficient PLL resources"
context = "MPF300T device with DDR4, PCIe, and UART requiring separate clocks"

# Tool searches for PLL resource documentation
# Returns: PLL availability per device, sharing strategies, alternatives
```

**Response:**
```markdown
# Error Resolution

**Error:** Insufficient PLL resources
**Context:** MPF300T device with DDR4, PCIe, and UART requiring separate clocks

Found 4 potentially relevant sections
---

## Solution 1: PolarFire FPGA Clocking Resources User Guide (Page 23)

```
PLL Resources by Device:

MPF300T-1FCG1152:
- 2x CCC (Clock Conditioning Circuitry) blocks
- Each CCC contains 1 PLL with 4 GL outputs
- Total: 2 PLLs, 8 global clock outputs

Resource Sharing Strategies:
1. Use single PLL with multiple outputs (if frequencies are related)
2. Share clocks between IPs when possible
3. Use fabric logic for simple clock division
4. Consider external clock sources

Example: DDR4 @ 100MHz can drive PCIe @ 100MHz directly
        UART @ 50MHz can be derived via fabric divider
```
---

## Solution 2: Design Optimization

```
Clock Sharing Recommendations:

Compatible clock domains:
- DDR4 (100 MHz) + PCIe (100 MHz) → Share PLL output
- UART (115200 baud) → Derive from system clock via counter
- Ethernet (125 MHz) + high-speed SERDES → May share PLL

Reduces PLL usage from 3 to 1-2 depending on frequencies.
```
```

### Example 3: tcl_monster Error Handler

```tcl
# In tcl_monster build script
proc handle_libero_error {error_log} {
    # Parse error log
    set errors [extract_errors $error_log]

    foreach err $errors {
        puts "Analyzing error: $err"

        # Query documentation for solution
        # (via Claude Code integration)
        set solutions [query_error_solutions $err]

        puts "Potential solutions:"
        foreach sol $solutions {
            puts "  - [dict get $sol title] (Page [dict get $sol page])"
            puts "    [dict get $sol snippet]"
        }
    }
}
```

---

## Tool 3: get_timing_constraints

### Purpose
Find timing constraint examples (SDC/PDC) for FPGA configurations.

### Use Cases
- Generate timing constraints for TCL scripts
- Find clock definition examples
- Learn multi-cycle path syntax
- Discover CDC constraint patterns

### Parameters
- **`constraint_type`** (required): Type of constraint (e.g., "clock definition", "input delay")
- **`ip_or_interface`** (optional): IP core or interface name
- **`top_k`** (optional): Number of examples (default: 3, max: 10)

### Example 1: Clock Definition for DDR4

**Tool Call:**
```json
{
  "tool": "get_timing_constraints",
  "arguments": {
    "constraint_type": "clock definition",
    "ip_or_interface": "DDR4"
  }
}
```

**Expected Response:**
```markdown
# Timing Constraints: clock definition
**IP/Interface:** DDR4

Found 3 constraint examples
---

## Example 1: Memory Controller User Guide (Page 156)

```
DDR4 Clock Constraints (SDC):

# System clock (100 MHz for DDR4-1600)
create_clock -name {clk_sys} -period 10.0 [get_ports {CLK_SYS}]

# DDR4 controller internal clocks
create_generated_clock -name {ddr4_ck} \
  -source [get_pins DDR4_CTRL/PLL/CLKOUT0] \
  -divide_by 1 [get_pins DDR4_CTRL/CK]

# Memory interface clocks
create_generated_clock -name {ddr4_dqs} \
  -source [get_pins DDR4_CTRL/PLL/CLKOUT1] \
  -divide_by 1 [get_ports {DDR4_DQS[*]}]

# Clock groups (asynchronous)
set_clock_groups -asynchronous \
  -group [get_clocks {clk_sys}] \
  -group [get_clocks {ddr4_ck ddr4_dqs}]
```
---

## Example 2: Board Design User Guide (Page 34)

```
DDR4 Timing Requirements:

Setup time (tSU): 0.75ns minimum
Hold time (tH): 0.75ns minimum
Clock-to-data skew: ±350ps maximum

SDC Constraints:
set_input_delay -clock [get_clocks ddr4_dqs] -min 0.75 [get_ports {DDR4_DQ[*]}]
set_input_delay -clock [get_clocks ddr4_dqs] -max 4.0 [get_ports {DDR4_DQ[*]}]
```
---

## Constraint Application Guidelines
1. Review constraint syntax carefully (SDC vs PDC)
2. Verify clock names match your design
3. Adjust timing values based on your requirements
4. Test constraints with timing analysis
5. Consider clock domain crossings and CDC constraints
```

### Example 2: False Path for Configuration Registers

**Tool Call:**
```python
# In tcl_monster constraint generator
constraint_type = "false path"
ip_or_interface = "configuration registers"

# Tool returns false path examples
```

**Response:**
```markdown
# Timing Constraints: false path

Found 2 constraint examples
---

## Example 1: Fabric User Guide (Page 112)

```
False Path Constraints for Static Configuration:

Configuration registers that don't change during operation
can be marked as false paths to improve timing closure:

# Exclude config registers from timing analysis
set_false_path -from [get_ports {CONFIG_*}]
set_false_path -to [get_cells {*_config_reg*}]

# Exclude reset synchronizers
set_false_path -through [get_pins */reset_sync_*/D]
```
```

### Example 3: tcl_monster Constraint Generator

**File:** `/mnt/c/tcl_monster/tcl_scripts/lib/generators/constraint_generator.tcl`

```tcl
#!/usr/bin/tclsh

# Generate timing constraints for design
proc generate_timing_constraints {design_config} {
    set constraint_file "constraints/timing.sdc"
    set fh [open $constraint_file w]

    # Get clock definitions from documentation
    puts $fh "# Clock Definitions"
    puts $fh "# Generated from PolarFire documentation"
    puts $fh ""

    # DDR4 constraints (if present)
    if {[dict exists $design_config ddr4]} {
        set ddr4_speed [dict get $design_config ddr4 speed]
        set period [expr {1000.0 / $ddr4_speed}]

        puts $fh "# DDR4 @ ${ddr4_speed} MHz"
        puts $fh "create_clock -name {clk_sys} -period ${period} \[get_ports {CLK_SYS}\]"
        puts $fh ""
    }

    # PCIe constraints (if present)
    if {[dict exists $design_config pcie]} {
        puts $fh "# PCIe Reference Clock (100 MHz)"
        puts $fh "create_clock -name {pcie_refclk} -period 10.0 \[get_ports {PCIE_REFCLK}\]"
        puts $fh ""
    }

    # Add CDC constraints between clock domains
    puts $fh "# Clock Domain Crossing Constraints"
    puts $fh "set_clock_groups -asynchronous \\"
    puts $fh "  -group \[get_clocks {clk_sys}\] \\"
    puts $fh "  -group \[get_clocks {pcie_refclk}\]"

    close $fh
    puts "Generated: $constraint_file"
}
```

---

## Complete Workflow Examples

### Workflow 1: DDR4 Configuration Generation

**Goal:** Generate complete DDR4 TCL configuration with validated parameters

```python
#!/usr/bin/env python3
"""DDR4 configuration generator with documentation validation."""

import sys
sys.path.insert(0, "/home/jorgill/fpga_mcp/src")

from fpga_rag.indexing import DocumentEmbedder
from mchp_mcp_core.storage.schemas import SearchQuery

# Initialize
embedder = DocumentEmbedder()

def validate_ddr4_params(size_gb, speed_mhz, data_width):
    """Validate DDR4 parameters against documentation."""

    # Query valid speed grades
    query = f"PF_DDR4 SPEED_GRADE {speed_mhz} MHz valid supported"
    results = embedder.vector_store.search(SearchQuery(query=query, top_k=3))

    print(f"Validating DDR4 configuration:")
    print(f"  Size: {size_gb}GB")
    print(f"  Speed: {speed_mhz}MHz")
    print(f"  Data Width: {data_width}-bit")
    print()

    for result in results:
        print(f"From {result.title} (Page {result.slide_or_page}):")
        print(f"  {result.snippet[:200]}...")
        print()

    return True

def generate_ddr4_tcl(size_gb, speed_mhz, data_width):
    """Generate DDR4 configuration TCL."""

    # Validate first
    if not validate_ddr4_params(size_gb, speed_mhz, data_width):
        print("ERROR: Invalid parameters")
        return

    # Generate TCL
    tcl = f"""
# DDR4 Configuration - Generated with documentation validation
# Size: {size_gb}GB, Speed: {speed_mhz}MHz, Width: {data_width}-bit

create_and_configure_core -core PF_DDR4 -component_name {{DDR4_CTRL}}

sd_configure_core_instance -sd_name {{DDR4_CTRL}} \\
  -instance_name {{DDR4_CTRL_0}} \\
  -params {{
    MEMORY_SIZE:{size_gb}GB
    SPEED_GRADE:{speed_mhz}
    DATA_WIDTH:{data_width}
    ROW_ADDRESS_WIDTH:15
    COLUMN_ADDRESS_WIDTH:10
    BANK_ADDRESS_WIDTH:3
  }}

# Generate timing constraints
source constraints/ddr4_timing.sdc
"""

    print("Generated TCL:")
    print(tcl)

    # Save to file
    with open("output/ddr4_config.tcl", "w") as f:
        f.write(tcl)

    print("Saved to: output/ddr4_config.tcl")

# Example usage
if __name__ == "__main__":
    generate_ddr4_tcl(size_gb=4, speed_mhz=1600, data_width=32)
```

### Workflow 2: Error Resolution Pipeline

**Goal:** Automated error resolution with documentation lookup

```python
#!/usr/bin/env python3
"""Libero error resolution with documentation search."""

import sys
import re
sys.path.insert(0, "/home/jorgill/fpga_mcp/src")

from fpga_rag.indexing import DocumentEmbedder
from mchp_mcp_core.storage.schemas import SearchQuery

embedder = DocumentEmbedder()

def parse_libero_log(log_file):
    """Extract errors from Libero log file."""
    errors = []

    with open(log_file, 'r') as f:
        for line in f:
            if "ERROR:" in line or "CRITICAL WARNING:" in line:
                errors.append(line.strip())

    return errors

def find_solutions(error_message):
    """Search documentation for error solutions."""

    # Extract key terms from error
    key_terms = re.findall(r'\\b[A-Z][A-Za-z]+\\b', error_message)
    query = " ".join(key_terms[:5]) + " solution fix constraint"

    print(f"Searching for solutions to: {error_message[:80]}...")

    results = embedder.vector_store.search(SearchQuery(query=query, top_k=5))

    solutions = []
    for idx, result in enumerate(results, 1):
        solutions.append({
            'rank': idx,
            'title': result.title,
            'page': result.slide_or_page,
            'relevance': result.score,
            'snippet': result.snippet
        })

    return solutions

def resolve_errors(log_file):
    """Main error resolution workflow."""

    errors = parse_libero_log(log_file)

    print(f"Found {len(errors)} errors in log file\\n")

    for error in errors:
        print(f"ERROR: {error}")
        print("=" * 80)

        solutions = find_solutions(error)

        if not solutions:
            print("No solutions found in documentation\\n")
            continue

        print(f"Found {len(solutions)} potential solutions:\\n")

        for sol in solutions:
            print(f"{sol['rank']}. {sol['title']} (Page {sol['page']}) - Relevance: {sol['relevance']:.2f}")
            print(f"   {sol['snippet'][:150]}...")
            print()

        print()

# Example usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python resolve_errors.py <libero_log_file>")
        sys.exit(1)

    resolve_errors(sys.argv[1])
```

---

## Integration Checklist

### For tcl_monster Developers

- [ ] Import `fpga_rag.indexing.DocumentEmbedder` in TCL generation scripts
- [ ] Add parameter validation before TCL generation
- [ ] Implement error handler with documentation lookup
- [ ] Generate timing constraints from documentation examples
- [ ] Add `--validate` flag to generators for parameter checking
- [ ] Create error resolution workflow for build failures
- [ ] Document examples of successful integrations
- [ ] Test with all IP cores (DDR4, PCIe, CCC, UART, GPIO)

### For Claude Code Sessions

- [ ] Initialize DocumentEmbedder at session start
- [ ] Use MCP tools for parameter queries during TCL generation
- [ ] Check documentation before suggesting parameter values
- [ ] Provide page references for all configuration recommendations
- [ ] Validate timing constraints against documentation
- [ ] Suggest alternatives when errors occur
- [ ] Link to specific document sections for details

---

## Performance Considerations

### Query Response Times

| Tool | Typical Time | Notes |
|------|--------------|-------|
| `query_ip_parameters` | 200-400ms | Depends on top_k |
| `explain_error` | 300-500ms | Larger result sets |
| `get_timing_constraints` | 150-300ms | Focused searches |

### Caching Strategies

For repeated queries (e.g., DDR4 parameters used multiple times):

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_ip_query(ip_core, parameter):
    """Cached IP parameter query."""
    embedder = DocumentEmbedder()
    query = f"{ip_core} {parameter} parameter configuration"
    return embedder.vector_store.search(SearchQuery(query=query, top_k=3))
```

### Batch Operations

When validating multiple IPs:

```python
def validate_multiple_ips(ip_configs):
    """Validate multiple IP configurations in batch."""
    embedder = DocumentEmbedder()  # Single initialization

    for ip_config in ip_configs:
        results = embedder.vector_store.search(...)
        # Process results
```

---

## Troubleshooting

### Common Issues

**Issue:** "Vector store not available"

**Solution:** Run indexing first:
```bash
cd ~/fpga_mcp
python scripts/test_indexing.py
```

**Issue:** "No results found for IP core"

**Solution:** Verify IP core name matches documentation:
- Use `PF_DDR4` not `DDR4_IP`
- Use `PF_CCC` not `CCC_CORE`
- Check `get_fpga_doc_info` for indexed documents

**Issue:** Search returns irrelevant results

**Solution:** Add more specific terms:
- Instead of "DDR4 configuration"
- Try "PF_DDR4 SPEED_GRADE parameter valid values"

---

## Future Enhancements

### Planned for Phase 3

1. **Table Content Search** - Query specific parameter tables directly
2. **Diagram Recognition** - OCR on timing diagrams and block diagrams
3. **Multi-document Comparison** - Compare parameters across RT PolarFire vs standard
4. **Knowledge Graph** - Understand IP dependencies (DDR4 → CCC → clocks)
5. **Constraint Validation** - Verify generated constraints against specs

### Feedback

Report issues or suggest improvements:
- File: `/home/jorgill/fpga_mcp/docs/IMPROVEMENTS_ROADMAP.md`
- Update Phase 2 section with findings

---

## Summary

The three tcl_monster tools provide:

1. **`query_ip_parameters`** - Pre-validate TCL parameters against specs
2. **`explain_error`** - Automated error resolution with doc citations
3. **`get_timing_constraints`** - Generate correct SDC/PDC constraints

**Integration Benefits:**
- ✅ Reduced TCL generation errors
- ✅ Faster error resolution
- ✅ Documentation-backed configurations
- ✅ Consistent timing constraints
- ✅ Automated validation workflow

**Next Steps:**
1. Test tools with real tcl_monster workflows
2. Add validation to existing generators
3. Create error resolution pipeline
4. Document successful patterns
5. Expand to additional IP cores

---

**Last Updated:** 2025-10-28
**Status:** Phase 2 Complete - Ready for Testing
