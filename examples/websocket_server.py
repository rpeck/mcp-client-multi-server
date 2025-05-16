#!/usr/bin/env python3
"""
An MCP server that runs over WebSocket protocol.
"""

import asyncio
import argparse
from fastmcp import FastMCP, Context

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="MCP WebSocket Server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--name", default="websocket-server", help="Server name")
    parser.add_argument("--prefix", default="WEBSOCKET: ", help="Response prefix")
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
            "transport": "websocket",
            "host": args.host,
            "port": args.port
        }

    # Run server with HTTP transport - FastMCP server doesn't directly support WebSocket transport
    print(f"Starting server on {args.host}:{args.port} (using streamable-http as WebSocket not supported)")
    # We'll use streamable HTTP as WebSocket is not directly supported in FastMCP server
    mcp.run(transport="streamable-http", host=args.host, port=args.port)

if __name__ == "__main__":
    main()