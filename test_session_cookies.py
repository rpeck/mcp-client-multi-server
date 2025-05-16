#!/usr/bin/env python3
"""
Test script for crunchbase cookies with single session.

This script connects to the crunchbase server, imports cookies, 
and then immediately uses them in the same session to test if they work.
"""

import os
import sys
import json
import logging
import asyncio
from mcp_client_multi_server.client import MultiServerClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_session_cookies")

async def main():
    # Create a standard transport
    url = "http://localhost:8000/mcp/stream"
    headers = {
        "X-Debug": "true",
        "X-Client": "single-session-test"
    }
    
    # Create MultiServerClient with config file
    client = MultiServerClient(config_path='examples/config.json')
    
    try:
        async with client:
            # First step: Initialize client and connection
            logger.info("Connecting to crunchbase server...")
            tools = await client.list_server_tools('crunchbase-http')
            logger.info(f"Available tools: {tools}")
            
            # Second step: Check authentication before importing cookies
            logger.info("Checking authentication status before importing cookies...")
            status = await client.query_server('crunchbase-http', tool_name='check_auth_status')
            print(f"Initial auth status: {status}")
            
            # Third step: Import cookies within the same session
            cookie_file = "/Users/rpeck/Source/mcp-projects/mcp-server-crunchbase/manual_cookies.json"
            if os.path.exists(cookie_file):
                logger.info(f"Importing cookies from {cookie_file}...")
                result = await client.query_server(
                    'crunchbase-http',
                    tool_name="import_browser_cookies", 
                    args={"cookie_file": cookie_file}
                )
                print(f"Import result: {result}")
                
                # Fourth step: Check authentication again in the same session
                logger.info("Checking authentication status after importing cookies...")
                status = await client.query_server('crunchbase-http', tool_name='check_auth_status')
                print(f"Authentication status after import: {status}")
                
                # Try to search for a company
                logger.info("Searching for Anthropic...")
                search_result = await client.query_server(
                    'crunchbase-http',
                    tool_name="search_company_name", 
                    args={"query": "Anthropic"}
                )
                print(f"Search result: {search_result}")
            else:
                logger.error(f"Cookie file not found: {cookie_file}")
    
    except Exception as e:
        logger.error(f"Error during test: {e}")
    
if __name__ == "__main__":
    asyncio.run(main())