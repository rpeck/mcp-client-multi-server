#!/usr/bin/env python
"""
Test script to verify the fix for the MCP Filesystem Server issue.
This tests the improved query_server method with different argument formats.
"""

import asyncio
import logging
import json
from pathlib import Path

from mcp_client_multi_server.client import MultiServerClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_fixed_client")

async def main():
    """Test different ways of calling the list_directory tool."""
    # Create client
    config_path = Path(__file__).parent / "examples" / "config.json"
    logger.info(f"Using config from: {config_path}")
    
    client = MultiServerClient(config_path=str(config_path), logger=logger, auto_launch=True)
    
    try:
        # Launch server
        logger.info("Launching filesystem server...")
        success = await client.launch_server("filesystem")
        
        if not success:
            logger.error("Failed to launch filesystem server.")
            return
        
        # Test different methods for listing directory
        logger.info("\n--- Method 1: Using args dictionary ---")
        response = await client.query_server(
            server_name="filesystem",
            tool_name="list_directory",
            args={"path": "/Users/rpeck"}
        )
        if response:
            logger.info(f"Success! Found {len(response)} items")
        else:
            logger.error("Failed to list directory")
        
        logger.info("\n--- Method 2: Using direct parameter ---")
        response = await client.query_server(
            server_name="filesystem",
            tool_name="list_directory",
            path="/Users/rpeck"
        )
        if response:
            logger.info(f"Success! Found {len(response)} items")
        else:
            logger.error("Failed to list directory")
        
        logger.info("\n--- Method 3: Using JSON string ---")
        json_path = json.dumps({"path": "/Users/rpeck"})
        response = await client.query_server(
            server_name="filesystem",
            tool_name="list_directory",
            message=json_path
        )
        if response:
            logger.info(f"Success! Found {len(response)} items")
        else:
            logger.error("Failed to list directory")
        
        # Test path restrictions (should fail with clear error message)
        logger.info("\n--- Testing path outside allowed directory ---")
        response = await client.query_server(
            server_name="filesystem",
            tool_name="list_directory",
            path="/"
        )
        if response:
            logger.info(f"Success! (unexpected) Found {len(response)} items")
        else:
            logger.info("Failed as expected (path outside allowed directory)")
            
        # Test read_file for comparison
        logger.info("\n--- Testing read_file ---")
        readme_path = "/Users/rpeck/Source/mcp-projects/mcp-client-multi-server/README.md"
        response = await client.query_server(
            server_name="filesystem",
            tool_name="read_file",
            path=readme_path
        )
        if response:
            logger.info(f"Success reading file!")
        else:
            logger.error("Failed to read file")
            
    except Exception as e:
        logger.exception(f"Error in test: {e}")
    finally:
        # Clean up
        logger.info("\nClosing client and stopping servers...")
        await client.close(stop_servers=True)
        
if __name__ == "__main__":
    asyncio.run(main())