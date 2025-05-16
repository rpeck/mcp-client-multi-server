#!/usr/bin/env python3
"""
MCP Multi-Server Client - A multi-server MCP client compatible with Claude Desktop configs.

This is the main CLI entry point for the MCP Multi-Server Client, providing commands
for listing servers, querying servers, listing tools, launching, and stopping servers.
For use as a module, import from mcp_client_multi_server directly.

This file delegates to the cli.py module for actual implementation.
"""

from mcp_client_multi_server.cli import main

if __name__ == "__main__":
    main()