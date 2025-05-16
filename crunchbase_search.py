#!/usr/bin/env python
"""
Crunchbase Search CLI

This script provides a command-line interface for searching companies on Crunchbase
using the MCP client and the Crunchbase MCP server.

Usage:
  python crunchbase_search.py company "Anthropic"  - Search for a company by name
  python crunchbase_search.py slug "anthropic"     - Get a company by its slug (more reliable with trial accounts)
  python crunchbase_search.py check                - Check authentication status
  python crunchbase_search.py import <cookie_file> - Import cookies from a file

Options:
  --config <path>                                  - Specify config file (default: examples/config.json)
  --server <name>                                  - Server name (default: crunchbase)

Prerequisites:
  1. The Crunchbase MCP server must be running
  2. The server must have valid authentication cookies
  3. See docs/CRUNCHBASE_INTEGRATION.md for details on setup
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("crunchbase_search")

# Add current directory to sys.path if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import MultiServerClient
try:
    from mcp_client_multi_server.client import MultiServerClient
except ImportError:
    logger.error("Could not import MultiServerClient. Make sure the package is installed.")
    sys.exit(1)

# Default configuration
DEFAULT_CONFIG_PATH = "examples/config.json"
DEFAULT_SERVER_NAME = "crunchbase"

def parse_response(response: Any) -> Dict:
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
                    continue
    
    # If we couldn't parse it as a dict, just return the original
    return response

async def check_auth_status(client: MultiServerClient, server_name: str) -> Dict:
    """Check authentication status with the Crunchbase server."""
    logger.info(f"Checking authentication status with {server_name}...")
    
    try:
        response = await client.query_server(
            server_name,
            tool_name="check_auth_status"
        )
        
        result = parse_response(response)
        return result
    except Exception as e:
        logger.error(f"Error checking authentication: {e}")
        return {"authenticated": False, "error": str(e)}

async def import_cookies(client: MultiServerClient, server_name: str, cookie_file: str) -> Dict:
    """Import cookies from a file to the Crunchbase server."""
    if not os.path.exists(cookie_file):
        logger.error(f"Cookie file not found: {cookie_file}")
        return {"success": False, "error": f"Cookie file not found: {cookie_file}"}
    
    logger.info(f"Importing cookies from {cookie_file}...")
    
    try:
        response = await client.query_server(
            server_name,
            tool_name="import_browser_cookies",
            args={"cookie_file": cookie_file}
        )
        
        result = parse_response(response)
        return result
    except Exception as e:
        logger.error(f"Error importing cookies: {e}")
        return {"success": False, "error": str(e)}

async def search_company(client: MultiServerClient, server_name: str, query: str) -> Dict:
    """Search for a company by name."""
    logger.info(f"Searching for company: {query}")
    
    try:
        response = await client.query_server(
            server_name,
            tool_name="search_company_name",
            args={"query": query}
        )
        
        result = parse_response(response)
        return result
    except Exception as e:
        logger.error(f"Error searching for company: {e}")
        return {"error": str(e)}

async def get_company_by_slug(client: MultiServerClient, server_name: str, slug: str) -> Dict:
    """Get a company by its slug."""
    logger.info(f"Getting company by slug: {slug}")
    
    try:
        response = await client.query_server(
            server_name,
            tool_name="get_company_by_slug",
            args={"slug": slug}
        )
        
        result = parse_response(response)
        return result
    except Exception as e:
        logger.error(f"Error getting company by slug: {e}")
        return {"error": str(e)}

def print_markdown(markdown: str) -> None:
    """Print markdown text with some basic formatting."""
    print("\n" + "=" * 80)
    print(markdown)
    print("=" * 80 + "\n")

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Crunchbase Search CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Company search command
    company_parser = subparsers.add_parser("company", help="Search for a company by name")
    company_parser.add_argument("query", help="Company name to search for")
    
    # Company by slug command
    slug_parser = subparsers.add_parser("slug", help="Get a company by its slug")
    slug_parser.add_argument("slug", help="Company slug (e.g., 'apple', 'microsoft')")
    
    # Check auth status command
    subparsers.add_parser("check", help="Check authentication status")
    
    # Import cookies command
    import_parser = subparsers.add_parser("import", help="Import cookies from a file")
    import_parser.add_argument("cookie_file", help="Path to the cookie file to import")
    
    # Optional config arguments
    parser.add_argument("--config", help="Path to config file", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--server", help="Server name", default=DEFAULT_SERVER_NAME)
    
    args = parser.parse_args()
    
    # Check if config file exists
    if not os.path.exists(args.config):
        logger.error(f"Config file not found: {args.config}")
        return 1
    
    # Create client
    client = MultiServerClient(config_path=args.config)
    
    try:
        async with client:
            # Run the appropriate command
            if args.command == "company":
                # First check auth status
                auth_status = await check_auth_status(client, args.server)
                if not auth_status.get("authenticated", False):
                    logger.error(f"Not authenticated: {auth_status.get('message', 'Unknown error')}")
                    print("\nTo authenticate, import cookies from your browser:")
                    print(f"  python crunchbase_search.py import <cookie_file>")
                    return 1
                
                # Search for the company
                result = await search_company(client, args.server, args.query)
                
                if "error" in result:
                    logger.error(f"Search failed: {result['error']}")
                    return 1
                
                if "markdown" in result:
                    print_markdown(result["markdown"])
                else:
                    print(json.dumps(result, indent=2))
                
            elif args.command == "slug":
                # First check auth status
                auth_status = await check_auth_status(client, args.server)
                if not auth_status.get("authenticated", False):
                    logger.error(f"Not authenticated: {auth_status.get('message', 'Unknown error')}")
                    print("\nTo authenticate, import cookies from your browser:")
                    print(f"  python crunchbase_search.py import <cookie_file>")
                    return 1
                
                # Get the company by slug
                result = await get_company_by_slug(client, args.server, args.slug)
                
                if "error" in result:
                    logger.error(f"Lookup failed: {result['error']}")
                    return 1
                
                if "markdown" in result:
                    print_markdown(result["markdown"])
                else:
                    print(json.dumps(result, indent=2))
                
            elif args.command == "check":
                # Check authentication status
                auth_status = await check_auth_status(client, args.server)
                
                print("\n=== Authentication Status ===")
                if auth_status.get("authenticated", False):
                    print(f"✅ Authenticated: {auth_status.get('message', 'Session is valid')}")
                else:
                    print(f"❌ Not authenticated: {auth_status.get('message', 'Unknown error')}")
                    print("\nTo authenticate, import cookies from your browser:")
                    print(f"  python crunchbase_search.py import <cookie_file>")
                
            elif args.command == "import":
                # Import cookies
                result = await import_cookies(client, args.server, args.cookie_file)
                
                if result.get("success", False):
                    print(f"✅ Cookies imported successfully: {result.get('message', '')}")
                    
                    # Check authentication after import
                    auth_status = await check_auth_status(client, args.server)
                    if auth_status.get("authenticated", False):
                        print(f"✅ Authentication successful: {auth_status.get('message', 'Session is valid')}")
                    else:
                        print(f"❌ Authentication failed: {auth_status.get('message', 'Unknown error')}")
                else:
                    print(f"❌ Cookie import failed: {result.get('error', 'Unknown error')}")
                    return 1
            else:
                parser.print_help()
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))