#!/usr/bin/env python3
"""
An MCP server that runs over Streamable HTTP protocol.
"""

import asyncio
import argparse
from fastmcp import FastMCP, Context

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="MCP Streamable HTTP Server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8767, help="Port to listen on")
    parser.add_argument("--name", default="streamable-http-server", help="Server name")
    parser.add_argument("--prefix", default="HTTP: ", help="Response prefix")
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
            "transport": "streamable-http",
            "host": args.host,
            "port": args.port
        }

    # Run server with Streamable HTTP transport
    print(f"Starting Streamable HTTP server on {args.host}:{args.port}")
    # FastMCP uses "streamable_http" (with underscore) as the transport name
    mcp.run(transport="streamable_http", host=args.host, port=args.port)

if __name__ == "__main__":
    main()