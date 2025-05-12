#!/usr/bin/env python3
"""
Agentix MCP Client - A multi-server MCP client compatible with Claude Desktop configs.
"""

import os
import sys
import json
import logging
import argparse
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from mcp_client_multi_server import MultiServerClient


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("mcp_client_multi_server")
    logger.setLevel(log_level)
    
    # Console handler
    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


async def list_servers(client: MultiServerClient, args: argparse.Namespace) -> None:
    """List all configured servers."""
    servers = client.list_servers()
    if not servers:
        print("No MCP servers configured.")
        return
        
    print("Configured MCP servers:")
    for server in servers:
        config = client.get_server_config(server)
        server_type = config.get("type", "unknown")
        url = config.get("url", "N/A")
        is_launchable = client._is_launchable(config)
        is_running = server in client._local_processes and client._local_processes[server].poll() is None
        status = "Running" if is_running else "Not running" if is_launchable else "N/A"
        print(f"  - {server} (Type: {server_type}, URL: {url}, Status: {status})")


async def query_server(client: MultiServerClient, args: argparse.Namespace) -> None:
    """Query a specific server with a message."""
    if not args.server:
        print("Error: --server argument is required")
        return
        
    # Optional message parameter
    message = None
    if args.message:
        message = args.message
        print(f"Querying server '{args.server}' with message: {args.message}")
    else:
        print(f"Querying server '{args.server}' with tool: {args.tool}")
        
    response = await client.query_server(args.server, message, tool_name=args.tool)
    
    if response:
        print("\nResponse:")
        # Handle TextContent objects from FastMCP
        if hasattr(response, '__iter__') and all(hasattr(item, 'text') for item in response):
            for item in response:
                print(item.text)
        else:
            print(response)
    else:
        print("\nNo response received or an error occurred.")


async def launch_server(client: MultiServerClient, args: argparse.Namespace) -> None:
    """Launch a local server."""
    if not args.server:
        print("Error: --server argument is required")
        return
        
    print(f"Launching server '{args.server}'...")
    success = await client.launch_server(args.server)
    
    if success:
        print(f"Server '{args.server}' launched successfully.")
    else:
        print(f"Failed to launch server '{args.server}'.")


async def stop_server(client: MultiServerClient, args: argparse.Namespace) -> None:
    """Stop a running local server."""
    if not args.server:
        print("Error: --server argument is required")
        return
        
    print(f"Stopping server '{args.server}'...")
    success = await client.stop_server(args.server)
    
    if success:
        print(f"Server '{args.server}' stopped successfully.")
    else:
        print(f"Failed to stop server '{args.server}'.")


async def list_tools(client: MultiServerClient, args: argparse.Namespace) -> None:
    """List all available tools on a server."""
    if not args.server:
        print("Error: --server argument is required")
        return
        
    print(f"Listing tools for server '{args.server}'...")
    tools = await client.list_server_tools(args.server)
    
    if not tools:
        print(f"No tools found on server '{args.server}' or failed to connect.")
        return
        
    print(f"\nTools available on server '{args.server}':")
    for tool in tools:
        print(f"  - {tool['name']}")
        if tool['description']:
            print(f"      Description: {tool['description']}")
        if tool['parameters']:
            print(f"      Parameters: {', '.join(tool['parameters'].keys())}")


async def main_async(args: argparse.Namespace) -> None:
    """Async main function."""
    logger = setup_logging(args.verbose)
    
    # Load custom configuration if provided
    custom_config = None
    if args.config:
        try:
            with open(args.config, "r") as f:
                custom_config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load config file: {e}")
            return
    
    # Create client
    client = MultiServerClient(
        config_path=args.config, 
        custom_config=custom_config,
        logger=logger,
        auto_launch=not args.no_auto_launch
    )
    
    try:
        # Execute the selected command
        if args.command == "list":
            await list_servers(client, args)
        elif args.command == "query":
            await query_server(client, args)
        elif args.command == "launch":
            await launch_server(client, args)
        elif args.command == "stop":
            await stop_server(client, args)
        elif args.command == "tools":
            await list_tools(client, args)
    finally:
        # Ensure we close all connections
        await client.close()


def main() -> None:
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(description="Multi-Server MCP Client")
    parser.add_argument("-c", "--config", help="Path to config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--no-auto-launch", action="store_true", help="Disable automatic server launching")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List servers command
    list_parser = subparsers.add_parser("list", help="List configured servers")
    
    # Query server command
    query_parser = subparsers.add_parser("query", help="Query a specific server")
    query_parser.add_argument("-s", "--server", required=True, help="Server name to query")
    query_parser.add_argument("-m", "--message", help="Message to send (optional for some tools)")
    query_parser.add_argument("-t", "--tool", default="process_message", help="Tool to call (default: process_message)")
    
    # Launch server command
    launch_parser = subparsers.add_parser("launch", help="Launch a local server")
    launch_parser.add_argument("-s", "--server", required=True, help="Server name to launch")
    
    # Stop server command
    stop_parser = subparsers.add_parser("stop", help="Stop a running local server")
    stop_parser.add_argument("-s", "--server", required=True, help="Server name to stop")
    
    # List tools command
    tools_parser = subparsers.add_parser("tools", help="List available tools on a server")
    tools_parser.add_argument("-s", "--server", required=True, help="Server name to query")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Run the async main
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()