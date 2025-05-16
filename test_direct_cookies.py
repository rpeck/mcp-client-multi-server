#!/usr/bin/env python3
"""
Direct curl-like test script for the crunchbase MCP server.

This script directly communicates with the crunchbase server, 
sending requests with the cookies from the session file.
"""

import os
import json
import asyncio
import httpx
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct_cookies_test")

# Path to the crunchbase session file
CRUNCHBASE_SESSION_FILE = "/Users/rpeck/Source/mcp-projects/mcp-server-crunchbase/.cb_session.json"
CRUNCHBASE_HTTP_URL = "http://localhost:8000/mcp/stream"

async def load_cookies() -> Dict[str, str]:
    """Load cookies from the session file."""
    try:
        if not os.path.exists(CRUNCHBASE_SESSION_FILE):
            logger.warning(f"Session file not found: {CRUNCHBASE_SESSION_FILE}")
            return {}
        
        with open(CRUNCHBASE_SESSION_FILE, "r") as f:
            cookies = json.load(f)
            logger.info(f"Loaded {len(cookies)} cookies from session file")
            return cookies
    except Exception as e:
        logger.error(f"Error loading session cookies: {e}")
        return {}

async def send_jsonrpc_request(
    url: str, 
    method: str, 
    params: Any = None, 
    cookies: Optional[Dict[str, str]] = None,
    request_id: int = 1,
) -> Dict[str, Any]:
    """Send a JSONRPC request to the server."""
    
    # Create JSONRPC message
    message = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id,
    }
    
    # Standard headers for MCP over HTTP
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",  # Accept both formats
        "X-Debug": "true",
        "X-Client": "direct-cookies-test",
    }
    
    logger.info(f"Sending {method} request to {url}")
    async with httpx.AsyncClient(cookies=cookies) as client:
        response = await client.post(
            url, 
            json=message,
            headers=headers,
        )
        
        # Check for session ID header
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            logger.info(f"Received session ID: {session_id}")
        
        # Return the JSON response
        try:
            return response.json()
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return {"error": f"Failed to parse response: {str(e)}"}

async def check_auth_status(url: str, cookies: Dict[str, str]) -> Dict[str, Any]:
    """Check the authentication status with the server."""
    return await send_jsonrpc_request(
        url,
        method="tools/call",
        params={"name": "check_auth_status", "arguments": {}},
        cookies=cookies,
    )

async def search_company(
    url: str, 
    cookies: Dict[str, str], 
    query: str
) -> Dict[str, Any]:
    """Search for a company by name."""
    return await send_jsonrpc_request(
        url,
        method="tools/call",
        params={"name": "search_company_name", "arguments": {"query": query}},
        cookies=cookies,
    )

async def list_tools(url: str, cookies: Dict[str, str]) -> Dict[str, Any]:
    """List all available tools on the server."""
    return await send_jsonrpc_request(
        url,
        method="tools/list",
        cookies=cookies,
    )

async def initialize_mcp_session(url: str, cookies: Dict[str, str]) -> Optional[str]:
    """Initialize an MCP session with the server."""
    # Initialize message
    init_message = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "sampling": {},
                "roots": {"listChanged": True}
            },
            "clientInfo": {
                "name": "direct-cookie-test",
                "version": "0.1.0"
            }
        },
        "id": 0
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "X-Debug": "true",
        "X-Client": "direct-cookies-test",
    }
    
    logger.info(f"Initializing MCP session with {url}")
    async with httpx.AsyncClient(cookies=cookies) as client:
        response = await client.post(
            url, 
            json=init_message,
            headers=headers,
        )
        
        # Check for session ID header
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            logger.info(f"Received session ID: {session_id}")
            return session_id
        else:
            logger.error("No session ID received")
            return None
        
async def send_initialized_notification(url: str, session_id: str, cookies: Dict[str, str]) -> None:
    """Send the initialized notification to the server."""
    # Notification message
    notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": None,
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "X-Debug": "true",
        "X-Client": "direct-cookies-test",
        "mcp-session-id": session_id,
    }
    
    logger.info(f"Sending initialized notification")
    async with httpx.AsyncClient(cookies=cookies) as client:
        response = await client.post(
            url, 
            json=notification,
            headers=headers,
        )
        
        if response.status_code == 202:
            logger.info("Initialized notification accepted")
        else:
            logger.error(f"Failed to send notification: {response.status_code}")

async def main():
    """Run the test against the crunchbase server."""
    
    # Load cookies from the session file
    cookies = await load_cookies()
    if not cookies:
        logger.error("No cookies loaded, cannot authenticate")
        return
    
    # Initialize MCP session
    session_id = await initialize_mcp_session(CRUNCHBASE_HTTP_URL, cookies)
    if not session_id:
        logger.error("Failed to initialize MCP session")
        return
        
    # Send initialized notification
    await send_initialized_notification(CRUNCHBASE_HTTP_URL, session_id, cookies)
    
    # Standard headers with session ID
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "X-Debug": "true",
        "X-Client": "direct-cookies-test",
        "mcp-session-id": session_id,
    }
    
    # Check authentication status
    logger.info("Checking authentication status...")
    
    # JSONRPC request for check_auth_status
    auth_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "check_auth_status", "arguments": {}},
        "id": 1,
    }
    
    async with httpx.AsyncClient(cookies=cookies) as client:
        auth_response = await client.post(
            CRUNCHBASE_HTTP_URL, 
            json=auth_request,
            headers=headers,
        )
        
        print("\nAuthentication Status:")
        print(json.dumps(auth_response.json(), indent=2))
    
    # List available tools
    logger.info("Listing available tools...")
    
    # JSONRPC request for tools/list
    tools_request = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": None,
        "id": 2,
    }
    
    async with httpx.AsyncClient(cookies=cookies) as client:
        tools_response = await client.post(
            CRUNCHBASE_HTTP_URL, 
            json=tools_request,
            headers=headers,
        )
        
        print("\nAvailable Tools:")
        print(json.dumps(tools_response.json(), indent=2))
    
    # Extract authentication info from response
    auth_info = auth_response.json()
    authenticated = False
    
    # Check for authenticated: true in the response
    try:
        result = auth_info.get("result", {})
        content = result.get("content", [{}])
        if content and isinstance(content, list) and len(content) > 0:
            content_text = content[0].get("text", "{}")
            if '"authenticated": true' in content_text:
                authenticated = True
    except Exception as e:
        logger.error(f"Error checking authentication: {e}")
    
    # Search for a company if authenticated
    if authenticated:
        logger.info("Authenticated, searching for 'Anthropic'...")
        
        # JSONRPC request for search_company_name
        search_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "search_company_name", "arguments": {"query": "Anthropic"}},
            "id": 3,
        }
        
        async with httpx.AsyncClient(cookies=cookies) as client:
            search_response = await client.post(
                CRUNCHBASE_HTTP_URL, 
                json=search_request,
                headers=headers,
            )
            
            print("\nSearch Result:")
            print(json.dumps(search_response.json(), indent=2))
    else:
        logger.warning("Not authenticated, skipping search")

if __name__ == "__main__":
    asyncio.run(main())