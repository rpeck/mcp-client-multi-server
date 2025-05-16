#!/usr/bin/env python3
"""
Test script for the filesystem MCP server.
Tests the listing of directories, file operations, and error handling.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from mcp_client_multi_server import MultiServerClient


async def test_filesystem_server() -> None:
    """Test the filesystem MCP server with various commands."""
    # Setup logging
    logger = logging.getLogger("mcp_client_multi_server")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Load configuration
    config_path = "examples/config.json"
    
    # Create client
    print("Creating MultiServerClient...")
    client = MultiServerClient(
        config_path=config_path,
        logger=logger,
        auto_launch=True
    )
    
    try:
        # Get allowed directories from the server first
        print("\n--- Testing getting allowed directories ---")
        response = await client.query_server(
            server_name="filesystem",
            tool_name="get_allowed_directories"
        )
        print(f"Allowed directories: {response}")
        
        # Test listing a directory (method 1: JSON string)
        print("\n--- Testing directory listing with JSON string ---")
        json_message = '{"path": "/Users/rpeck"}'
        response = await client.query_server(
            server_name="filesystem",
            tool_name="list_directory",
            message=json_message
        )
        print(f"Directory listing (JSON string method): {response}")
        
        # Test listing a directory (method 2: args dict)
        print("\n--- Testing directory listing with args dict ---")
        response = await client.query_server(
            server_name="filesystem",
            tool_name="list_directory",
            args={"path": "/Users/rpeck"}
        )
        print(f"Directory listing (args dict method): {response}")
        
        # Test listing a directory (method 3: kwargs)
        print("\n--- Testing directory listing with kwargs ---")
        response = await client.query_server(
            server_name="filesystem",
            tool_name="list_directory",
            path="/Users/rpeck"
        )
        print(f"Directory listing (kwargs method): {response}")
        
        # Test reading a file
        print("\n--- Testing file reading ---")
        response = await client.query_server(
            server_name="filesystem",
            tool_name="read_file",
            args={"path": "/Users/rpeck/.bashrc"}
        )
        # Truncate the output if it's too large
        if response and len(str(response)) > 500:
            print(f"File content (truncated): {str(response)[:500]}...")
        else:
            print(f"File content: {response}")
        
        # Test error handling - path outside allowed directories
        print("\n--- Testing error handling (path outside allowed directories) ---")
        try:
            response = await client.query_server(
                server_name="filesystem",
                tool_name="list_directory",
                args={"path": "/etc"}
            )
            print(f"Response (should be an error): {response}")
        except Exception as e:
            print(f"Expected error: {e}")
        
        # Test error handling - invalid path
        print("\n--- Testing error handling (invalid path) ---")
        response = await client.query_server(
            server_name="filesystem",
            tool_name="list_directory",
            args={"path": "/Users/rpeck/nonexistent_directory"}
        )
        print(f"Response (should indicate directory not found): {response}")
        
    finally:
        # Clean up
        print("\nClosing client and stopping servers...")
        await client.close(stop_servers=True)


if __name__ == "__main__":
    asyncio.run(test_filesystem_server())