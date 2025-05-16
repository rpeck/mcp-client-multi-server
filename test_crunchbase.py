#!/usr/bin/env python3
"""Test connecting to crunchbase server with the multi-server client using HTTP transport."""

import asyncio
import json
import logging
import os
from mcp_client_multi_server.client import MultiServerClient

# Set up logging
logging.basicConfig(level=logging.DEBUG)

async def main():
    # Initialize client with config file
    print("Initializing client...")
    client = MultiServerClient(config_path='examples/config.json')
    
    try:
        # List available servers
        print("Listing servers...")
        servers = client.list_servers()
        print(f"Available servers: {servers}")
        
        # Connect to the crunchbase server via HTTP transport
        print("Connecting to crunchbase server via HTTP...")
        tools = await client.list_server_tools('crunchbase-http')
        if tools:
            print(f"Available tools: {json.dumps(tools, indent=2)}")
        else:
            print("Failed to get tools list")
            return
        
        # Try import_browser_cookies with simplified args
        cookie_file = "/Users/rpeck/Source/mcp-projects/mcp-server-crunchbase/manual_cookies.json"
        if os.path.exists(cookie_file):
            print(f"\nCookie file found at: {cookie_file}")
            
            # First check the authentication status
            print("Checking authentication status...")
            auth_status = await client.query_server(
                'crunchbase-http', 
                tool_name='check_auth_status',
                args={}
            )
            print(f"Authentication status: {auth_status}")
            
            print("Testing import_browser_cookies tool...")
            # Try direct RPC style with our fixed server
            import_result = await client.query_server(
                'crunchbase-http', 
                tool_name='import_browser_cookies',
                args={"cookie_file": cookie_file}
            )
            print(f"import_browser_cookies result: {import_result}")
            
            # Check authentication status again after importing cookies
            print("\nChecking authentication status after importing cookies...")
            auth_status = await client.query_server(
                'crunchbase-http', 
                tool_name='check_auth_status',
                args={}
            )
            print(f"Authentication status: {auth_status}")
            
            # Try with get_company_by_slug
            print("\nTesting get_company_by_slug tool...")
            company_result = await client.query_server(
                'crunchbase-http', 
                tool_name='get_company_by_slug',
                args={"slug": "anthropic"}
            )
            print(f"get_company_by_slug result: {company_result}")
            
            # Try search_company_name if either of the above worked
            if import_result or company_result:
                print("\nTesting search_company_name tool...")
                search_result = await client.query_server(
                    'crunchbase-http', 
                    tool_name='search_company_name',
                    args={"query": "Anthropic"}
                )
                print(f"search_company_name result: {search_result}")
        else:
            print(f"Cookie file not found at: {cookie_file}")
    finally:
        # Close the client and connections
        print("Closing client connections...")
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())