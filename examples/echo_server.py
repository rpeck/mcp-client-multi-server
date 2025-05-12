#!/usr/bin/env python3
"""
A simple MCP server that echoes messages back.
"""

import asyncio
import argparse
from fastmcp import FastMCP, Context


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Simple MCP Echo Server")
    parser.add_argument("--name", default="echo-server", help="Server name")
    parser.add_argument("--prefix", default="ECHO: ", help="Response prefix")
    args = parser.parse_args()

    # Initialize MCP server
    mcp = FastMCP(args.name)
    prefix = args.prefix

    @mcp.tool()
    async def process_message(message: str, ctx: Context) -> str:
        """Process a user message and echo it back."""
        await ctx.info(f"Received message: {message}")
        return f"{prefix}{message}"

    @mcp.tool()
    async def ping() -> str:
        """Simple ping tool for testing connectivity."""
        return "pong"

    # Run server with stdio transport (for Claude Desktop)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()