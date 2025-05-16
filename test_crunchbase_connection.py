#!/usr/bin/env python
"""
Test script to verify connection to Crunchbase server with updated cookies.
"""

import os
import sys
import asyncio
import logging
import json
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("test_connection")

# Add the client multi-server package path to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import MultiServerClient
try:
    from mcp_client_multi_server.client import MultiServerClient
except ImportError:
    logger.error("Could not import MultiServerClient. Make sure the package is installed.")
    sys.exit(1)

def parse_response(response):
    """Parse response from the server, which may be a list of text content or a dict."""
    # If it's already a dict, return it
    if isinstance(response, dict):
        return response
        
    # If it's a list of text content, parse the JSON from the text
    if isinstance(response, list):
        for item in response:
            if hasattr(item, 'text'):
                try:
                    return json.loads(item.text)
                except json.JSONDecodeError:
                    logger.warning(f"Couldn't parse as JSON: {item.text}")
    
    # Return the original response if we couldn't parse it
    return response

async def prepare_cookie_file():
    """Prepare a cookie file for the test by copying .cb_session.json."""
    source_path = "/Users/rpeck/Source/mcp-projects/mcp-server-crunchbase/.cb_session.json"
    dest_path = "temp_cookies.json"
    
    try:
        # Copy the file
        shutil.copy2(source_path, dest_path)
        logger.info(f"Copied cookies from {source_path} to {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"Error copying cookie file: {e}")
        return None

async def test_crunchbase_connection():
    """Test connection to the Crunchbase server and basic functionality."""
    logger.info("Testing connection to Crunchbase server with updated cookies")
    
    # Create client with config file
    config_path = 'examples/config.json'
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        return False
        
    # Prepare cookie file
    cookie_file = await prepare_cookie_file()
    if not cookie_file:
        logger.error("Failed to prepare cookie file")
        return False
    
    client = MultiServerClient(config_path=config_path)
    
    try:
        async with client:
            # Step 1: Connect to the server
            logger.info("Connecting to Crunchbase server...")
            
            # Use crunchbase-http server directly
            crunchbase_server = "crunchbase-http"
            
            # List tools for the server
            try:
                tools = await client.list_server_tools(crunchbase_server)
                logger.info(f"Available tools: {tools}")
            except Exception as e:
                logger.error(f"Failed to list tools: {e}")
                return False
            
            # Step 2: Check authentication status (before importing cookies)
            logger.info("Checking authentication status (before importing cookies)...")
            try:
                status_response = await client.query_server(
                    crunchbase_server,
                    tool_name='check_auth_status'
                )
                
                # Parse the response
                status = parse_response(status_response)
                logger.info(f"Initial authentication status: {status}")
            except Exception as e:
                logger.error(f"Failed to check initial auth status: {e}")
            
            # Step 3: Import cookies
            logger.info(f"Importing cookies from {cookie_file}...")
            try:
                import_response = await client.query_server(
                    crunchbase_server,
                    tool_name='import_browser_cookies',
                    args={"cookie_file": cookie_file}
                )
                
                # Parse the response
                import_result = parse_response(import_response)
                logger.info(f"Import result: {import_result}")
                
                if isinstance(import_result, dict) and not import_result.get('success', False):
                    logger.error(f"Failed to import cookies: {import_result.get('error', 'Unknown error')}")
                    return False
            except Exception as e:
                logger.error(f"Failed to import cookies: {e}")
                return False
            
            # Step 4: Check authentication status (after importing cookies)
            logger.info("Checking authentication status (after importing cookies)...")
            try:
                status_response = await client.query_server(
                    crunchbase_server,
                    tool_name='check_auth_status'
                )
                
                # Parse the response
                status = parse_response(status_response)
                logger.info(f"Updated authentication status: {status}")
                
                if isinstance(status, dict) and not status.get('authenticated', False):
                    logger.error("Still not authenticated after importing cookies.")
                    logger.error("The cookies may be expired or invalid.")
                    return False
            except Exception as e:
                logger.error(f"Failed to check updated auth status: {e}")
                return False
                
            # Step 5: Try a simple search
            logger.info("Testing search functionality...")
            try:
                search_response = await client.query_server(
                    crunchbase_server,
                    tool_name="search_company_name",
                    args={"query": "Anthropic"}
                )
                
                # Parse the response
                search_result = parse_response(search_response)
                logger.info(f"Search result type: {type(search_result)}")
                
                if isinstance(search_result, dict) and "error" in search_result:
                    logger.error(f"Search failed: {search_result.get('error')}")
                    return False
                    
                logger.info("Search successful!")
                logger.info("Connection test passed! Cookies are working correctly.")
                return True
            except Exception as e:
                logger.error(f"Failed to search: {e}")
                return False
                
    except Exception as e:
        logger.error(f"Error creating client: {e}")
        return False
    finally:
        # Clean up temporary cookie file
        if cookie_file and os.path.exists(cookie_file):
            try:
                os.remove(cookie_file)
                logger.info(f"Cleaned up temporary cookie file: {cookie_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary cookie file: {e}")

async def main():
    """Main function to run the test."""
    success = await test_crunchbase_connection()
    if success:
        logger.info("✅ All tests passed! The Crunchbase server is working correctly with the updated cookies.")
    else:
        logger.error("❌ Test failed. There are still issues with the Crunchbase server connection.")
    
    return 0 if success else 1

if __name__ == "__main__":
    asyncio.run(main())