#!/usr/bin/env python3
"""
Test script to validate the behavior of server lifecycle management in MultiServerClient.

This script:
1. Creates a MultiServerClient
2. Checks which servers would be considered STDIO servers
3. Simulates various closing behaviors
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any

from mcp_client_multi_server.client import MultiServerClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_client_behavior")


async def main():
    """Main test function."""
    print("Testing MultiServerClient server lifecycle management")
    print("-" * 50)

    # Load test configuration
    config_path = Path("examples/config.json")
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        return
    
    # Create client
    client = MultiServerClient(config_path=config_path, logger=logger)
    
    # List all servers and check their STDIO status
    servers = client.list_servers()
    print(f"Found {len(servers)} configured servers:")
    
    for server in servers:
        config = client.get_server_config(server)
        server_type = config.get("type", "unknown")
        url = config.get("url", "N/A")
        is_launchable = client._is_launchable(config)
        is_stdio = client._is_local_stdio_server(server)
        running, pid = client._is_server_running(server)
        
        print(f"  - {server}:")
        print(f"    Type: {server_type}")
        print(f"    URL: {url}")
        print(f"    Launchable: {is_launchable}")
        print(f"    Is STDIO server: {is_stdio}")
        print(f"    Running: {running} (PID: {pid})")
    
    print("-" * 50)
    print("Testing server launch and close behavior:")
    
    # Find first launchable server
    launchable_server = None
    for server in servers:
        config = client.get_server_config(server)
        if client._is_launchable(config):
            launchable_server = server
            break
    
    if not launchable_server:
        print("No launchable servers found in config.")
        await client.close(stop_servers=False)
        return
    
    print(f"Testing with server: {launchable_server}")
    
    # Launch the server
    print(f"Launching server {launchable_server}...")
    success = await client.launch_server(launchable_server)
    
    if success:
        print(f"Successfully launched {launchable_server}")
        running, pid = client._is_server_running(launchable_server)
        print(f"Server running: {running} (PID: {pid})")
        is_stdio = client._is_local_stdio_server(launchable_server)
        print(f"Is STDIO server: {is_stdio}")
        
        # Close with stop_servers=True
        print("Closing client with stop_servers=True...")
        await client.close(stop_servers=True)
        
        # Check if server is still running
        running, pid = client._is_server_running(launchable_server)
        print(f"After closing with stop_servers=True, server running: {running} (PID: {pid})")
    else:
        print(f"Failed to launch {launchable_server}")
    
    print("-" * 50)
    
    # Create a new client and launch again
    print("Creating a new client instance and launching server again...")
    client = MultiServerClient(config_path=config_path, logger=logger)
    
    success = await client.launch_server(launchable_server)
    if success:
        print(f"Successfully launched {launchable_server}")
        running, pid = client._is_server_running(launchable_server)
        print(f"Server running: {running} (PID: {pid})")
        
        # Close with stop_servers=False
        print("Closing client with stop_servers=False...")
        await client.close(stop_servers=False)
        
        # Check if server is still running
        running, pid = client._is_server_running(launchable_server)
        print(f"After closing with stop_servers=False, server running: {running} (PID: {pid})")
        
        # Clean up - stop the server
        if running:
            print("Cleaning up - stopping the server...")
            await client.stop_server(launchable_server)
    else:
        print(f"Failed to launch {launchable_server}")
    
    print("-" * 50)
    print("Test completed.")


if __name__ == "__main__":
    asyncio.run(main())