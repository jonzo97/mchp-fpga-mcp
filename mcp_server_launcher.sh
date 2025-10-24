#!/bin/bash
# Launcher script for FPGA Documentation MCP Server

cd "$(dirname "$0")"
export PYTHONPATH="$HOME/fpga_mcp/src:$HOME/mchp-mcp-core:$PYTHONPATH"

python src/fpga_rag/mcp_server/server.py
