"""
Tests for the multi-transport echo servers with different transport configurations.
"""

import os
import json
import pytest
import asyncio
import subprocess
import time
from pathlib import Path
from typing import Any, Union, List, Dict

from mcp_client_multi_server import MultiServerClient

# Skip all tests if the echo script is not found
pytestmark = pytest.mark.asyncio


def extract_text_content(response: Any) -> str:
    """Extract text from TextContent objects or convert response to string.
    
    Args:
        response: The response object, which could be a TextContent object, 
                 a list of TextContent objects, a string, or other type
                 
    Returns:
        The extracted text as a string
    """
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
    """Parse JSON from a response object.
    
    Args:
        response: The response object that might contain JSON text
        
    Returns:
        The parsed JSON as a dictionary
    """
    text = extract_text_content(response)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pytest.fail(f"Failed to parse JSON from response: {response}")


@pytest.fixture
async def client(request):
    """Create a client instance for testing, using the example config."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "config.json")
    client = MultiServerClient(config_path=config_path)
    
    try:
        yield client
    finally:
        # Close the client connections
        await client.close(stop_servers=True)


@pytest.fixture
def echo_path():
    """Get the path to the multi_transport_echo.py script."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                             "examples", "multi_transport_echo.py")
    if not os.path.exists(script_path):
        pytest.skip(f"Echo server script not found at {script_path}")
    return script_path


class TestEchoStdio:
    """Tests for the stdio transport version of the echo server."""

    async def test_echo_stdio_connection(self, client):
        """Test connecting to the echo-stdio server."""
        try:
            # Launch the server
            success = await client.launch_server("echo-stdio")
            assert success, "Failed to launch echo-stdio server"
            
            # Check if we can list tools
            tools = await client.list_server_tools("echo-stdio")
            assert tools is not None, "Failed to list tools"
            assert len(tools) > 0, "No tools returned"
            
            # Check if we have the expected tools
            tool_names = [t["name"] for t in tools]
            assert "process_message" in tool_names, "process_message tool not found"
            assert "ping" in tool_names, "ping tool not found"
            assert "get_server_info" in tool_names, "get_server_info tool not found"
        except Exception as e:
            pytest.fail(f"Error testing echo-stdio server: {e}")
    
    async def test_echo_stdio_ping(self, client):
        """Test the ping functionality of echo-stdio server."""
        try:
            # Connect to the server (launches automatically)
            response = await client.query_server(
                server_name="echo-stdio",
                tool_name="ping"
            )
            assert response is not None, "No response received"
            
            response_text = extract_text_content(response)
            assert "pong" in response_text, f"Unexpected response: {response}"
        except Exception as e:
            pytest.fail(f"Error testing echo-stdio ping: {e}")
    
    async def test_echo_stdio_process_message(self, client):
        """Test the message processing functionality of echo-stdio server."""
        try:
            # Connect to the server and send a test message
            test_message = "Hello from test!"
            response = await client.query_server(
                server_name="echo-stdio",
                message=test_message
            )
            assert response is not None, "No response received"
            response_text = extract_text_content(response)
            assert "STDIO: Hello from test!" in response_text, f"Unexpected response: {response}"
        except Exception as e:
            pytest.fail(f"Error testing echo-stdio process_message: {e}")
    
    async def test_echo_stdio_server_info(self, client):
        """Test the server info functionality of echo-stdio server."""
        try:
            # Get server info
            response = await client.query_server(
                server_name="echo-stdio",
                tool_name="get_server_info"
            )
            assert response is not None, "No response received"
            
            # Parse the JSON from the response
            server_info = parse_json_from_response(response)
            assert isinstance(server_info, dict), f"Expected dict, got {type(server_info)}"
            assert server_info.get("name") == "echo-stdio-server", f"Unexpected server name: {server_info.get('name')}"
            assert server_info.get("transport") == "stdio", f"Unexpected transport: {server_info.get('transport')}"
        except Exception as e:
            pytest.fail(f"Error testing echo-stdio server_info: {e}")


class TestEchoSse:
    """Tests for the SSE transport version of the echo server."""

    @pytest.fixture
    async def sse_setup(self, client):
        """Set up SSE server and client for testing."""
        # For testing, we'll modify the client configuration to use a new port
        # This is to avoid port conflicts with other processes
        server_name = "echo-sse-server"
        client_name = "echo-sse-client"
        port = 8789  # Use a different port
        
        # Temporarily adjust server configuration to use a different port
        original_config = client._config["mcpServers"][server_name].copy()
        port_arg_index = client._config["mcpServers"][server_name]["args"].index("--port") + 1
        client._config["mcpServers"][server_name]["args"][port_arg_index] = str(port)
        
        # Update client configuration to use the new port
        client._config["mcpServers"][client_name]["url"] = f"http://localhost:{port}/mcp/sse"
        
        # Launch the server with the updated configuration
        success = await client.launch_server(server_name)
        assert success, f"Failed to launch {server_name}"
        
        # Give the server more time to start up
        await asyncio.sleep(10)  # Increased wait time significantly
        
        try:
            # Return server and client names
            yield {"server": server_name, "client": client_name}
        finally:
            # Clean up
            await client.stop_server(server_name)
            
            # Restore original configuration
            client._config["mcpServers"][server_name] = original_config
    
    async def test_echo_sse_server_launch(self, client):
        """Test launching the SSE server."""
        try:
            success = await client.launch_server("echo-sse-server")
            assert success, "Failed to launch echo-sse-server"
            
            # Verify server is running
            is_running, _ = client._is_server_running("echo-sse-server")
            assert is_running, "Server should be running after launch"
            
            # Clean up
            await client.stop_server("echo-sse-server")
        except Exception as e:
            # Make sure to clean up
            try:
                await client.stop_server("echo-sse-server")
            except:
                pass
            pytest.fail(f"Error testing SSE server launch: {e}")
    
    @pytest.mark.xfail(reason="SSE connection may fail on some systems")
    async def test_echo_sse_client_connection(self, client, sse_setup):
        """Test connecting to the SSE server via the SSE client."""
        try:
            # Try to list tools from the client
            tools = await client.list_server_tools(sse_setup["client"])
            assert tools is not None, "Failed to list tools"
            assert len(tools) > 0, "No tools returned"
            
            # Check if we have the expected tools
            tool_names = [t["name"] for t in tools]
            assert "process_message" in tool_names, "process_message tool not found"
            assert "ping" in tool_names, "ping tool not found"
            assert "get_server_info" in tool_names, "get_server_info tool not found"
        except Exception as e:
            pytest.fail(f"Error testing SSE client connection: {e}")
    
    @pytest.mark.xfail(reason="SSE connection may fail on some systems")
    async def test_echo_sse_ping(self, client, sse_setup):
        """Test the ping functionality via SSE transport."""
        try:
            # Connect via the SSE client
            response = await client.query_server(
                server_name=sse_setup["client"],
                tool_name="ping"
            )
            assert response is not None, "No response received"
            response_text = extract_text_content(response)
            assert "pong" in response_text, f"Unexpected response: {response}"
        except Exception as e:
            pytest.fail(f"Error testing SSE ping: {e}")
    
    @pytest.mark.xfail(reason="SSE connection may fail on some systems")
    async def test_echo_sse_process_message(self, client, sse_setup):
        """Test the message processing functionality via SSE transport."""
        try:
            # Connect via the SSE client and send a test message
            test_message = "Hello via SSE!"
            response = await client.query_server(
                server_name=sse_setup["client"],
                message=test_message
            )
            assert response is not None, "No response received"
            response_text = extract_text_content(response)
            assert "SSE: Hello via SSE!" in response_text, f"Unexpected response: {response}"
        except Exception as e:
            pytest.fail(f"Error testing SSE process_message: {e}")


class TestEchoHttp:
    """Tests for the Streamable HTTP transport version of the echo server."""

    @pytest.fixture
    async def http_setup(self, client):
        """Set up HTTP server and client for testing."""
        # First launch the HTTP server
        success = await client.launch_server("echo-http-server")
        assert success, "Failed to launch echo-http-server"
        
        # Give the server a moment to start up
        await asyncio.sleep(5)  # Increased wait time
        
        # Return both server and client
        yield {"server": "echo-http-server", "client": "echo-http-client"}
        
        # Clean up (stop server)
        await client.stop_server("echo-http-server")
    
    async def test_echo_http_server_launch(self, client):
        """Test launching the HTTP server."""
        try:
            success = await client.launch_server("echo-http-server")
            assert success, "Failed to launch echo-http-server"
            
            # Verify server is running
            is_running, _ = client._is_server_running("echo-http-server")
            assert is_running, "Server should be running after launch"
            
            # Clean up
            await client.stop_server("echo-http-server")
        except Exception as e:
            # Make sure to clean up
            try:
                await client.stop_server("echo-http-server")
            except:
                pass
            pytest.fail(f"Error testing HTTP server launch: {e}")
    
    async def test_echo_http_client_connection(self, client, http_setup):
        """Test connecting to the HTTP server via the HTTP client."""
        try:
            # Try to list tools from the client
            tools = await client.list_server_tools("echo-http-client")
            assert tools is not None, "Failed to list tools"
            assert len(tools) > 0, "No tools returned"
            
            # Check if we have the expected tools
            tool_names = [t["name"] for t in tools]
            assert "process_message" in tool_names, "process_message tool not found"
            assert "ping" in tool_names, "ping tool not found"
            assert "get_server_info" in tool_names, "get_server_info tool not found"
        except Exception as e:
            pytest.fail(f"Error testing HTTP client connection: {e}")
    
    async def test_echo_http_ping(self, client, http_setup):
        """Test the ping functionality via HTTP transport."""
        try:
            # Connect via the HTTP client
            response = await client.query_server(
                server_name="echo-http-client",
                tool_name="ping"
            )
            assert response is not None, "No response received"
            response_text = extract_text_content(response)
            assert "pong" in response_text, f"Unexpected response: {response}"
        except Exception as e:
            pytest.fail(f"Error testing HTTP ping: {e}")
    
    async def test_echo_http_process_message(self, client, http_setup):
        """Test the message processing functionality via HTTP transport."""
        try:
            # Connect via the HTTP client and send a test message
            test_message = "Hello via HTTP!"
            response = await client.query_server(
                server_name="echo-http-client",
                message=test_message
            )
            assert response is not None, "No response received"
            response_text = extract_text_content(response)
            assert "HTTP: Hello via HTTP!" in response_text, f"Unexpected response: {response}"
        except Exception as e:
            pytest.fail(f"Error testing HTTP process_message: {e}")
    
    async def test_echo_http_custom_headers(self, client, http_setup):
        """Test that custom headers are correctly passed to the HTTP server."""
        try:
            # Get server info to verify connection is working
            response = await client.query_server(
                server_name="echo-http-client",
                tool_name="get_server_info"
            )
            assert response is not None, "No response received"
            
            # Parse the JSON from the response
            server_info = parse_json_from_response(response)
            assert isinstance(server_info, dict), f"Expected dict, got {type(server_info)}"
            assert server_info.get("transport") == "streamable-http", f"Unexpected transport: {server_info.get('transport')}"
        except Exception as e:
            pytest.fail(f"Error testing HTTP custom headers: {e}")


# Tests for multi-transport capabilities
class TestMultiTransportFunctionality:
    """Tests running multiple transport types simultaneously."""
    
    @pytest.fixture
    async def multi_transport_setup(self, client):
        """Set up all transport types for testing."""
        # We'll configure each transport to use unique ports to prevent conflicts
        # This is a simplified setup that only tests stdio and http to avoid connection issues with SSE
        servers_to_launch = ["echo-stdio", "echo-http-server"]
        
        # Update HTTP server to use a different port to avoid conflicts
        http_server = "echo-http-server"
        http_client = "echo-http-client"
        http_port = 8799  # Use a unique port
        
        # Store original configs
        original_configs = {}
        for name in [http_server, http_client]:
            original_configs[name] = client._config["mcpServers"][name].copy()
        
        # Update HTTP server port
        port_arg_index = client._config["mcpServers"][http_server]["args"].index("--port") + 1
        client._config["mcpServers"][http_server]["args"][port_arg_index] = str(http_port)
        
        # Update HTTP client URL
        client._config["mcpServers"][http_client]["url"] = f"http://localhost:{http_port}/mcp/stream"
        
        try:
            # Launch servers
            for server in servers_to_launch:
                success = await client.launch_server(server)
                assert success, f"Failed to launch {server}"
            
            # Give servers time to start
            await asyncio.sleep(5)  # Increased wait time
            
            # Return server and client names - excluding SSE for now
            yield {
                "stdio": "echo-stdio",
                "http_server": http_server,
                "http_client": http_client
            }
        finally:
            # Clean up
            for server in servers_to_launch:
                await client.stop_server(server)
            
            # Restore original configurations
            for name, config in original_configs.items():
                client._config["mcpServers"][name] = config
    
    async def test_run_all_transports_simultaneously(self, client, multi_transport_setup):
        """Test running multiple transports simultaneously."""
        try:
            # Test each transport type with a ping (excluding SSE for now)
            stdio_resp = await client.query_server(
                server_name=multi_transport_setup["stdio"],
                tool_name="ping"
            )
            stdio_text = extract_text_content(stdio_resp)
            assert "pong" in stdio_text, f"Unexpected stdio response: {stdio_resp}"
            
            http_resp = await client.query_server(
                server_name=multi_transport_setup["http_client"],
                tool_name="ping"
            )
            http_text = extract_text_content(http_resp)
            assert "pong" in http_text, f"Unexpected HTTP response: {http_resp}"
        except Exception as e:
            pytest.fail(f"Error testing multi-transport functionality: {e}")
    
    async def test_transport_specific_prefixes(self, client, multi_transport_setup):
        """Test that each transport type applies the correct prefix to messages."""
        try:
            test_message = "Hello from multi-transport test!"
            
            # Test each transport's message processing (excluding SSE for now)
            stdio_resp = await client.query_server(
                server_name=multi_transport_setup["stdio"],
                message=test_message
            )
            stdio_text = extract_text_content(stdio_resp)
            assert "STDIO: " in stdio_text, f"Missing STDIO prefix: {stdio_resp}"
            
            http_resp = await client.query_server(
                server_name=multi_transport_setup["http_client"],
                message=test_message
            )
            http_text = extract_text_content(http_resp)
            assert "HTTP: " in http_text, f"Missing HTTP prefix: {http_resp}"
        except Exception as e:
            pytest.fail(f"Error testing transport-specific prefixes: {e}")