#!/usr/bin/env python3
"""
A multi-transport MCP server that echoes messages back using multiple transport protocols.
This server can be configured to run with stdio, SSE, or streamable-http transport.
"""

import asyncio
import argparse
from fastmcp import FastMCP, Context


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Multi-Transport MCP Echo Server")
    parser.add_argument("--name", default="echo-server", help="Server name")
    parser.add_argument("--prefix", default="ECHO: ", help="Response prefix")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"],
                      help="Transport protocol to use")
    parser.add_argument("--host", default="localhost", help="Host to bind to (for network transports)")
    parser.add_argument("--port", type=int, default=0, help="Port to listen on (0 = auto-assign)")
    args = parser.parse_args()
    
    # Use port if specified, otherwise use defaults for each transport
    if args.port == 0:
        if args.transport == "sse":
            args.port = 8766
        elif args.transport == "streamable-http":
            args.port = 8767
    
    print(f"Starting {args.name} using {args.transport} transport")
    if args.transport != "stdio":
        print(f"Listening on {args.host}:{args.port}")

    # Initialize MCP server
    mcp = FastMCP(args.name)
    prefix = args.prefix

    @mcp.tool()
    async def process_message(message: str, ctx: Context) -> str:
        """Process a user message and echo it back."""
        await ctx.info(f"Received message: {message}")
        response = f"{prefix}{message}"
        print(f"Sending response: {response}")
        return response

    @mcp.tool()
    async def ping() -> str:
        """Simple ping tool for testing connectivity."""
        print("Received ping request")
        return "pong"

    @mcp.tool()
    async def get_server_info() -> dict:
        """Get server information."""
        info = {
            "name": args.name,
            "transport": args.transport,
        }
        if args.transport != "stdio":
            info["host"] = args.host
            info["port"] = args.port
        return info

    # Run server with specified transport
    transport_kwargs = {}
    if args.transport in ["sse", "streamable-http"]:
        transport_kwargs = {
            "host": args.host,
            "port": args.port
        }
    
    mcp.run(transport=args.transport, **transport_kwargs)


if __name__ == "__main__":
    main()