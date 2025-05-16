#!/usr/bin/env python3
"""
An MCP server that runs over Server-Sent Events (SSE) protocol.
"""

import asyncio
import argparse
from fastmcp import FastMCP, Context

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="MCP SSE Server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8766, help="Port to listen on")
    parser.add_argument("--name", default="sse-server", help="Server name")
    parser.add_argument("--prefix", default="SSE: ", help="Response prefix")
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

    @mcp.tool()
    async def get_server_info() -> dict:
        """Get server information."""
        return {
            "name": args.name,
            "transport": "sse",
            "host": args.host,
            "port": args.port
        }

    # Run server with SSE transport
    print(f"Starting SSE server on {args.host}:{args.port}")
    # Make sure we use the correct transport name for FastMCP
    mcp.run(transport="sse", host=args.host, port=args.port)

if __name__ == "__main__":
    main()