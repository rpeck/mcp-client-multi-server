#!/usr/bin/env python
"""
Test script for npx-based MCP servers.
"""

import asyncio
import logging
import sys
from pathlib import Path

from mcp_client_multi_server.client import MultiServerClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("npx_test")


async def test_server(client, server_name):
    """Test connecting to and using a specific server."""
    logger.info(f"Testing server: {server_name}")
    
    # First, try connecting
    logger.info(f"Connecting to {server_name}...")
    try:
        await client.connect(server_name)
        logger.info(f"✅ Successfully connected to {server_name}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to {server_name}: {e}")
        return False
    
    # List available tools
    logger.info(f"Listing tools on {server_name}...")
    try:
        tools = await client.list_server_tools(server_name)
        logger.info(f"✅ Successfully listed tools on {server_name}:")
        for tool in tools:
            logger.info(f"  - {tool['name']}: {tool['description']}")
    except Exception as e:
        logger.error(f"❌ Failed to list tools on {server_name}: {e}")
        return False
    
    return True


async def main():
    """Test npx-based MCP servers."""
    logger.info("Testing npx-based MCP servers...")
    
    # Create client with example configuration
    config_path = Path("examples/config.json")
    client = MultiServerClient(config_path=config_path, logger=logger)
    
    # Get all server names
    server_names = client.list_servers()
    logger.info(f"Found servers: {server_names}")
    
    # Track success/failure
    results = {}
    
    try:
        # Test each server
        for server_name in server_names:
            config = client.get_server_config(server_name)
            cmd = config.get("command", "")
            
            # Only test npx servers
            if "npx" in cmd or cmd.endswith("npx"):
                logger.info(f"Testing npx server: {server_name}")
                success = await test_server(client, server_name)
                results[server_name] = success
            else:
                logger.info(f"Skipping non-npx server: {server_name}")
    finally:
        # Clean up
        logger.info("Closing client...")
        await client.close()
    
    # Show results
    logger.info("\n=== Test Results ===")
    all_success = True
    for server_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{server_name}: {status}")
        if not success:
            all_success = False
    
    # Set exit code based on results
    if not all_success:
        logger.error("Some tests failed!")
        sys.exit(1)
    else:
        logger.info("All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())