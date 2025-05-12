#!/usr/bin/env python3
"""
Simple script to test Playwright server port handling.
"""

import asyncio
import logging
from pathlib import Path
from mcp_client_multi_server.client import MultiServerClient

async def main():
    # Set up logging
    logger = logging.getLogger("playwright_test")
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Path to config file
    config_path = Path(__file__).parent / "examples" / "config.json"
    
    # Create client
    client = MultiServerClient(config_path=str(config_path), logger=logger)
    
    try:
        # Try to connect to the Playwright server
        logger.info("Attempting to connect to Playwright server...")
        playwright_client = await client.connect("playwright")
        
        if playwright_client:
            logger.info("Successfully connected to Playwright server")
            
            # Check if we can list tools
            async with playwright_client:
                try:
                    tools = await playwright_client.list_tools()
                    tool_names = [tool.name for tool in tools]
                    logger.info(f"Found {len(tools)} tools: {tool_names}")
                except Exception as e:
                    logger.error(f"Error listing tools: {e}")
        else:
            logger.error("Failed to connect to Playwright server")
    except Exception as e:
        logger.error(f"Error connecting to Playwright server: {e}")
    finally:
        # Clean up
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())