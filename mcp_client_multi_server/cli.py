"""
MCP Multi-Server Client command-line interface.

This module provides the command-line interface for the MCP Multi-Server Client.
It handles parsing arguments, setting up logging, and executing commands.
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
        # Check if server is running (either in local processes or in registry)
        is_running, pid = client._is_server_running(server)

        if is_running:
            status = f"Running (PID: {pid})"
        else:
            status = "Not running" if is_launchable else "N/A"

        print(f"  - {server} (Type: {server_type}, URL: {url}, Status: {status})")


async def query_server(client: MultiServerClient, args: argparse.Namespace) -> None:
    """Query a specific server with a message."""
    if not args.server:
        print("Error: --server argument is required", file=sys.stderr)
        return
        
    # Set server-specific defaults
    tool_name = args.tool
    if args.server == "fetch" and tool_name == "process_message":
        # Special case: fetch server uses 'fetch' as its default tool
        tool_name = "fetch"
        
    # Optional message parameter
    message = None
    if args.message:
        message = args.message
        print(f"Querying server '{args.server}' with message: {args.message}")
    else:
        print(f"Querying server '{args.server}' with tool: {tool_name}")
        
    # Enhanced error handling for JSON messages
    if args.message and args.message.strip().startswith('{'):
        try:
            # Validate JSON format
            parsed_json = json.loads(args.message)
            print("JSON message format detected and validated")
            
            # Special notice for fetch server with JSON
            if args.server == "fetch" and "url" in parsed_json:
                print(f"Using URL: {parsed_json['url']}")
        except json.JSONDecodeError as e:
            print(f"Warning: Message looks like JSON but has syntax errors: {e}", file=sys.stderr)
            print("The server may reject this message. Please check your JSON format.", file=sys.stderr)
            return

    # Add special handling for filesystem server
    if args.server == "filesystem":
        # For list_directory test for path access before executing
        if tool_name == "list_directory" and message:
            try:
                # Parse the JSON message to check the path
                if isinstance(message, str) and message.strip().startswith('{'):
                    try:
                        params = json.loads(message)
                        if "path" in params:
                            path = params["path"]
                            # Check for obvious security violations
                            if not path.startswith("/Users/rpeck"):
                                print(f"\nAccess denied: The path '{path}' is outside the allowed directories.", file=sys.stderr)
                                print("The filesystem server is only allowed to access paths under /Users/rpeck", file=sys.stderr)
                                print("\nFor filesystem server, make sure your query includes a valid path within allowed directories.", file=sys.stderr)
                                print("Example: --message '{\"path\": \"/Users/rpeck\"}'", file=sys.stderr)
                                # No need to even try the request, return early
                                return
                    except json.JSONDecodeError:
                        # Already checked above, just continue
                        pass
            except Exception as e:
                print(f"Error parsing message: {e}", file=sys.stderr)
    
    # Execute the query
    try:
        response = await client.query_server(args.server, message, tool_name=tool_name)
        
        # Display the response if successful
        if response:
            print("\nResponse:")
            # Handle TextContent objects from FastMCP
            if hasattr(response, '__iter__') and all(hasattr(item, 'text') for item in response):
                for item in response:
                    print(item.text)
            else:
                print(response)
        else:
            print("\nNo response received or the server returned an empty response.", file=sys.stderr)
            
            # Special error handling for filesystem server when response is None
            if args.server == "filesystem":
                print("\nFor filesystem server, make sure your query includes a valid path within allowed directories.", file=sys.stderr)
                print("Example: --message '{\"path\": \"/Users/rpeck\"}'", file=sys.stderr)
                
                # Show allowed directories
                try:
                    allowed_dirs = await client.query_server(args.server, tool_name="list_allowed_directories")
                    if allowed_dirs:
                        print(f"\nAllowed directories: {allowed_dirs}", file=sys.stderr)
                except Exception:
                    pass
    except Exception as e:
        # Handle specific exception types better
        print(f"\nError: {e}", file=sys.stderr)
        
        # Special error handling for filesystem server
        if args.server == "filesystem":
            error_str = str(e)
            if "path outside allowed directories" in error_str:
                print("\nAccess denied: The path you tried to access is outside the allowed directories.", file=sys.stderr)
            elif "ENOENT" in error_str or "no such file or directory" in error_str:
                print("\nFile or directory not found. Please check that the path exists.", file=sys.stderr)
            elif "EACCES" in error_str or "permission denied" in error_str:
                print("\nPermission denied. The server doesn't have access to this path.", file=sys.stderr)
            
            print("\nFor filesystem server, make sure your query includes a valid path within allowed directories.", file=sys.stderr)
            print("Example: --message '{\"path\": \"/Users/rpeck\"}'", file=sys.stderr)
            
            # Show allowed directories
            try:
                allowed_dirs = await client.query_server(args.server, tool_name="list_allowed_directories")
                if allowed_dirs:
                    print(f"\nAllowed directories: {allowed_dirs}", file=sys.stderr)
            except Exception:
                pass
        
        # Special handling for Crunchbase server
        if args.server == "crunchbase":
            error_str = str(e)
            if "authenticated" in error_str.lower() or "login" in error_str.lower():
                print("\nAuthentication issue detected. Please check your Crunchbase cookies:", file=sys.stderr)
                print("1. Run the Easy Login Tool (see docs/CRUNCHBASE_INTEGRATION.md)", file=sys.stderr)
                print("2. Or run: python crunchbase_search.py check", file=sys.stderr)


async def launch_server(client: MultiServerClient, args: argparse.Namespace) -> None:
    """Launch a local server and keep it running."""
    if not args.server:
        print("Error: --server argument is required")
        return

    print(f"Launching server '{args.server}'...")
    success = await client.launch_server(args.server)

    if success:
        print(f"Server '{args.server}' launched successfully.")
        print(f"Server will continue running as a background process.")
        print(f"Use 'stop' command to stop it when done: python -m mcp_client_multi_server stop --server {args.server}")
        print(f"Server logs will be stored in: ~/.mcp-client-multi-server/logs/")
    else:
        # Get the log file paths for the server
        log_info = client.get_server_logs(args.server)
        stderr_log = log_info.get('stderr')
        
        print(f"Failed to launch server '{args.server}'.", file=sys.stderr)
        
        if stderr_log and os.path.exists(stderr_log):
            # Read the last few lines from the stderr log
            try:
                with open(stderr_log, 'r') as f:
                    stderr_lines = f.readlines()
                    last_lines = stderr_lines[-10:] if len(stderr_lines) > 10 else stderr_lines
                    stderr_content = ''.join(last_lines)
                
                if stderr_content.strip():
                    print("\nError details:", file=sys.stderr)
                    print(stderr_content, file=sys.stderr)
            except Exception as e:
                print(f"Error reading log file: {e}", file=sys.stderr)
        
        print("\nThis may be caused by missing dependencies or configuration issues.", file=sys.stderr)
        print(f"Full logs are available at: ~/.mcp-client-multi-server/logs/", file=sys.stderr)


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
        print(f"Failed to stop server '{args.server}'. The server may not be running or there was an error during shutdown.")


async def stop_all_servers(client: MultiServerClient, args: argparse.Namespace) -> None:
    """Stop all running servers."""
    print("Stopping all running servers...")
    results = await client.stop_all_servers()

    if not results:
        print("No servers were running.")
        return

    success_count = sum(1 for success in results.values() if success)
    print(f"Stopped {success_count} of {len(results)} servers.")

    # Print details
    for server_name, success in results.items():
        status = "stopped successfully" if success else "failed to stop"
        print(f"  - '{server_name}': {status}")


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
        elif args.command == "stop-all":
            await stop_all_servers(client, args)
        elif args.command == "tools":
            await list_tools(client, args)
    finally:
        # Track the state of running STDIO servers before closing
        stdio_servers = []
        for server_name in client._local_processes:
            if client._is_local_stdio_server(server_name):
                proc = client._local_processes[server_name]
                if proc and proc.poll() is None:  # If process is still running
                    stdio_servers.append(server_name)

        # Ensure we close all connections
        if stdio_servers and args.command not in ["stop", "stop-all", "launch"]:
            print(f"Automatically stopping {len(stdio_servers)} local STDIO server(s): {', '.join(stdio_servers)}")
            # Close client and stop local STDIO servers
            await client.close(stop_servers=True)
        else:
            # Close client connections but don't stop any servers
            await client.close(stop_servers=False)


def main() -> None:
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(description="MCP Multi-Server Client")
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
    query_parser.add_argument("-a", "--args", help="JSON-encoded arguments for the tool (alternative to message)")
    
    # Launch server command
    launch_parser = subparsers.add_parser("launch", help="Launch a local server")
    launch_parser.add_argument("-s", "--server", required=True, help="Server name to launch")
    
    # Stop server command
    stop_parser = subparsers.add_parser("stop", help="Stop a running local server")
    stop_parser.add_argument("-s", "--server", required=True, help="Server name to stop")

    # Stop all servers command
    stop_all_parser = subparsers.add_parser("stop-all", help="Stop all running servers")

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