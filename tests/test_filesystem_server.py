"""
Tests for the filesystem server.

These tests verify that the filesystem server can be launched,
and basic file operations work as expected.
"""

import os
import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Dict, Any

from mcp_client_multi_server import MultiServerClient

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    """Create a client instance for testing, using the example config."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "config.json")
    client = MultiServerClient(config_path=config_path)
    
    try:
        yield client
    finally:
        # Close the client connections
        await client.close(stop_servers=True)


def extract_text_content(response: Any) -> str:
    """Extract text from TextContent objects or convert response to string."""
    # Handle None case
    if response is None:
        return "None"
    
    # Handle list of TextContent objects
    if hasattr(response, '__iter__') and not isinstance(response, (str, dict)) and hasattr(response, '__len__'):
        if len(response) > 0 and all(hasattr(item, 'text') for item in response):
            return response[0].text
    # Handle single TextContent object
    elif hasattr(response, 'text'):
        return response.text
    # Handle dictionary with text field
    elif isinstance(response, dict) and 'text' in response:
        return response['text']
    # Default to string conversion
    return str(response)


def parse_json_from_response(response: Any) -> Dict:
    """Parse JSON from a response object."""
    text = extract_text_content(response)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pytest.fail(f"Failed to parse JSON from response: {response}")


class TestFilesystemServer:
    """Tests for the filesystem server."""
    
    async def test_server_launch(self, client):
        """Test launching the filesystem server."""
        try:
            # Attempt to launch the server
            success = await client.launch_server("filesystem")
            assert success, "Failed to launch filesystem server"
            
            # Verify server is running
            is_running, _ = client._is_server_running("filesystem")
            assert is_running, "Server should be running after launch"
        finally:
            # Clean up
            await client.stop_server("filesystem")
    
    async def test_tool_listing(self, client):
        """Test listing tools from the filesystem server."""
        try:
            # Launch the server
            success = await client.launch_server("filesystem")
            assert success, "Failed to launch filesystem server"
            
            # List tools
            tools = await client.list_server_tools("filesystem")
            assert tools is not None, "Failed to list tools"
            assert len(tools) > 0, "No tools returned"
            
            # Check for expected tools
            tool_names = [t["name"] for t in tools]
            expected_tools = [
                "read_file", "write_file", "list_directory", "create_directory"
            ]
            
            for tool in expected_tools:
                assert tool in tool_names, f"{tool} tool not found"
        finally:
            # Clean up
            await client.stop_server("filesystem")
    
    @pytest.mark.skip(reason="Requires modifying server configuration to point to a test directory")
    async def test_list_directory(self, client):
        """Test the listDirectory tool."""
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files
            test_file_1 = Path(temp_dir) / "test1.txt"
            test_file_2 = Path(temp_dir) / "test2.txt"
            test_file_1.write_text("Test content 1")
            test_file_2.write_text("Test content 2")
            
            # Create a test subdirectory
            test_subdir = Path(temp_dir) / "subdir"
            test_subdir.mkdir()
            
            try:
                # Launch the server (modified to point to temp_dir)
                # Note: This would require modifying the configuration dynamically
                # which is beyond the scope of this test
                success = await client.launch_server("filesystem")
                assert success, "Failed to launch filesystem server"
                
                # List directory (assuming server is configured to use temp_dir)
                response = await client.query_server(
                    server_name="filesystem",
                    tool_name="list_directory",
                    path="."  # Root directory of server's configured path
                )
                
                # Basic response validation
                assert response is not None, "No response received"
                dir_listing = parse_json_from_response(response)
                assert isinstance(dir_listing, list), "Expected list response"
                
                # Verify test files are in the listing
                file_names = [item["name"] for item in dir_listing]
                assert "test1.txt" in file_names, "test1.txt not found in directory listing"
                assert "test2.txt" in file_names, "test2.txt not found in directory listing"
                assert "subdir" in file_names, "subdir not found in directory listing"
            finally:
                # Clean up
                await client.stop_server("filesystem")
    
    @pytest.mark.xfail(reason="Requires proper configuration pointing to a readable area of the filesystem")
    async def test_read_file(self, client):
        """Test the readFile tool (marked as xfail due to configuration requirements)."""
        try:
            # Launch the server
            success = await client.launch_server("filesystem")
            assert success, "Failed to launch filesystem server"
            
            # Try to read a file that should exist in most Unix environments
            # Note: This might fail depending on filesystem permissions and the
            # server's configured root directory
            response = await client.query_server(
                server_name="filesystem",
                tool_name="read_file",
                path="/etc/hosts"  # This path should be accessible in most Unix systems
            )
            
            # Basic response validation
            assert response is not None, "No response received"
            content = extract_text_content(response)
            assert "localhost" in content, "Expected 'localhost' in /etc/hosts content"
        finally:
            # Clean up
            await client.stop_server("filesystem")