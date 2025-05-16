"""
Integration tests for various transport types using real servers.
This test module does not use mocks - it tests against real servers.
"""

import os
import sys
import asyncio
import pytest
import time
import signal
import subprocess
from pathlib import Path

from mcp_client_multi_server.client import (
    MultiServerClient,
    NpxProcessTransport,
    UvxProcessTransport,
)
from fastmcp.client.transports import (
    WSTransport,
    SSETransport,
    StreamableHttpTransport
)


class TestTransportIntegration:
    """
    Integration tests for various transport types using real servers.
    These tests launch actual servers and connect to them.
    """

    def _assert_response_contains(self, response, expected_text):
        """Helper method to assert response content regardless of format."""
        if isinstance(response, str):
            assert response == expected_text
        elif hasattr(response, 'text'):  # Single TextContent
            assert response.text == expected_text
        elif isinstance(response, list) and len(response) > 0:
            # Handle TextContent objects in a list
            if hasattr(response[0], 'text'):
                assert response[0].text == expected_text
            else:
                assert str(response) == expected_text
        else:
            # For dictionaries and other objects
            assert expected_text in str(response)
    
    @pytest.fixture
    async def client(self):
        """Create MultiServerClient instance with the example config."""
        # Get the absolute path to the example config
        config_path = Path(__file__).parent.parent / "examples" / "config.json"

        # Create the client
        client = MultiServerClient(config_path=config_path, auto_launch=True)

        # Yield the client for tests to use
        yield client

        # Clean up after tests by stopping all servers
        await client.stop_all_servers()
    
    @pytest.mark.asyncio
    async def test_stdio_transport(self, client):
        """Test stdio transport with the echo server."""
        # Connect to the echo server
        echo_client = await client.connect("echo")
        assert echo_client is not None

        # Send a message and verify response
        response = await client.query_server("echo", "Hello from stdio test")

        self._assert_response_contains(response, "ECHO: Hello from stdio test")
    
    @pytest.mark.skip(reason="FastMCP server doesn't directly support WebSocket transport")
    @pytest.mark.asyncio
    async def test_websocket_transport(self, client):
        """
        Test WebSocket transport.
        Note: This test is skipped because FastMCP server doesn't directly support WebSocket.
        In a real environment, you would use a separate WebSocket server.
        """
        # First launch the WebSocket server
        await client.launch_server("websocket-server")
        # Give it time to start
        await asyncio.sleep(2)

        # Connect to the WebSocket server via the client config
        ws_client = await client.connect("websocket-client")
        assert ws_client is not None

        # Send a message via the websocket client
        try:
            response = await client.query_server("websocket-client", "Hello from WebSocket test")
            self._assert_response_contains(response, "WEBSOCKET: Hello from WebSocket test")

            # Test ping tool
            ping_response = await client.query_server("websocket-client", tool_name="ping")
            self._assert_response_contains(ping_response, "pong")

            # Get server info to verify it's the right server
            info = await client.query_server("websocket-client", tool_name="get_server_info")
            assert "websocket" in info
            assert "localhost" in info
            assert "8765" in info
        except Exception as e:
            pytest.fail(f"WebSocket test failed: {e}")
        finally:
            # Clean up
            await client.stop_server("websocket-server")
    
    @pytest.mark.asyncio
    async def test_sse_transport(self, client):
        """Test Server-Sent Events (SSE) transport."""
        # First launch the SSE server
        await client.launch_server("sse-server")
        # Give it time to start
        await asyncio.sleep(2)
        
        # Connect to the SSE server via the client config
        sse_client = await client.connect("sse-client")
        assert sse_client is not None
        
        # Send a message via the SSE client
        try:
            response = await client.query_server("sse-client", "Hello from SSE test")
            self._assert_response_contains(response, "SSE: Hello from SSE test")

            # Test ping tool
            ping_response = await client.query_server("sse-client", tool_name="ping")
            self._assert_response_contains(ping_response, "pong")
            
            # Get server info to verify it's the right server
            info = await client.query_server("sse-client", tool_name="get_server_info")
            assert "sse" in info
            assert "localhost" in info
            assert "8766" in info
        except Exception as e:
            pytest.fail(f"SSE test failed: {e}")
        finally:
            # Clean up
            await client.stop_server("sse-server")
    
    @pytest.mark.asyncio
    async def test_streamable_http_transport(self, client):
        """Test Streamable HTTP transport."""
        # First launch the Streamable HTTP server
        await client.launch_server("streamable-http-server")
        # Give it time to start
        await asyncio.sleep(2)
        
        # Connect to the Streamable HTTP server via the client config
        http_client = await client.connect("streamable-http-client")
        assert http_client is not None
        
        # Send a message via the Streamable HTTP client
        try:
            response = await client.query_server("streamable-http-client", "Hello from HTTP test")
            self._assert_response_contains(response, "HTTP: Hello from HTTP test")

            # Test ping tool
            ping_response = await client.query_server("streamable-http-client", tool_name="ping")
            self._assert_response_contains(ping_response, "pong")
            
            # Get server info to verify it's the right server
            info = await client.query_server("streamable-http-client", tool_name="get_server_info")
            assert "streamable-http" in info
            assert "localhost" in info
            assert "8767" in info
        except Exception as e:
            pytest.fail(f"Streamable HTTP test failed: {e}")
        finally:
            # Clean up
            await client.stop_server("streamable-http-server")
    
    @pytest.mark.asyncio
    async def test_npx_transport(self, client):
        """Test NPX transport with the filesystem server."""
        # The filesystem server is configured in the example config
        try:
            # Connect to the filesystem server
            filesystem_client = await client.connect("filesystem")
            assert filesystem_client is not None
            
            # List tools to verify connection
            tools = await client.list_server_tools("filesystem")
            assert tools is not None
            
            # Find list_directory tool
            list_dir_tool = next((t for t in tools if t["name"] == "list_directory"), None)
            assert list_dir_tool is not None
            
            # Call list_directory tool
            # Use /tmp which should exist on all systems
            response = await client.query_server(
                "filesystem", 
                tool_name="list_directory", 
                args={"path": "/tmp"}
            )
            assert isinstance(response, list)
        except Exception as e:
            pytest.fail(f"NPX transport test failed: {e}")
        finally:
            await client.stop_server("filesystem")
    
    @pytest.mark.asyncio
    async def test_transport_type_creation(self, client):
        """
        Test that correct transport types are created from configuration.
        This ensures our transport factory logic works correctly.
        """
        # Test WebSocket transport creation
        websocket_config = client.get_server_config("websocket-client")
        ws_transport = client._create_transport_from_config("websocket-client", websocket_config)
        assert isinstance(ws_transport, WSTransport)
        assert ws_transport.url == "ws://localhost:8765"

        # Inspect the WebSocket transport
        print(f"WebSocket transport: {ws_transport!r}")
        print(f"WebSocket transport attributes: {dir(ws_transport)}")
        for attr in ['url', '_ping_interval', '_ping_timeout', '_max_size', 'compression']:
            if hasattr(ws_transport, attr):
                print(f"  {attr}: {getattr(ws_transport, attr)}")

        # Test SSE transport creation
        sse_config = client.get_server_config("sse-client")
        sse_transport = client._create_transport_from_config("sse-client", sse_config)
        assert isinstance(sse_transport, SSETransport)
        assert sse_transport.url == "http://localhost:8766/mcp/sse"

        # Inspect the SSE transport
        print(f"SSE transport: {sse_transport!r}")
        print(f"SSE transport attributes: {dir(sse_transport)}")
        for attr in ['url', 'headers']:
            if hasattr(sse_transport, attr):
                print(f"  {attr}: {getattr(sse_transport, attr)}")

        # Test Streamable HTTP transport creation
        http_config = client.get_server_config("streamable-http-client")
        http_transport = client._create_transport_from_config("streamable-http-client", http_config)
        assert isinstance(http_transport, StreamableHttpTransport)
        assert http_transport.url == "http://localhost:8767/mcp/stream"

        # Inspect the Streamable HTTP transport
        print(f"Streamable HTTP transport: {http_transport!r}")
        print(f"Streamable HTTP transport attributes: {dir(http_transport)}")
        for attr in ['url', 'headers']:
            if hasattr(http_transport, attr):
                print(f"  {attr}: {getattr(http_transport, attr)}")

        # Test NPX transport creation
        npx_config = client.get_server_config("filesystem")
        npx_transport = client._create_transport_from_config("filesystem", npx_config)
        assert isinstance(npx_transport, NpxProcessTransport)
        assert npx_transport.package == "@modelcontextprotocol/server-filesystem"

        # Inspect the NPX transport
        print(f"NPX transport: {npx_transport!r}")
        print(f"NPX transport attributes: {dir(npx_transport)}")
        for attr in ['package', 'npx_path', 'server_args', 'command', 'args', 'env']:
            if hasattr(npx_transport, attr):
                print(f"  {attr}: {getattr(npx_transport, attr)}")

        # The test passes if all transports are created with correct types
        # This validates that our transport creation logic works correctly
        # even if we can't test actual communication with all transports
    
    @pytest.mark.asyncio
    async def test_multiple_clients_simultaneously(self, client):
        """Test connecting to multiple servers with different transport types simultaneously."""
        # Launch all servers (except WebSocket which we've skipped)
        await client.launch_server("echo")
        await client.launch_server("sse-server")
        await client.launch_server("streamable-http-server")
        
        # Give servers time to start
        await asyncio.sleep(3)
        
        try:
            # Connect to all clients (except WebSocket which doesn't work with FastMCP)
            echo_client = await client.connect("echo")
            sse_client = await client.connect("sse-client")
            http_client = await client.connect("streamable-http-client")

            # Check that all connections succeeded
            assert echo_client is not None
            assert sse_client is not None
            assert http_client is not None

            # Define tasks for concurrent querying
            async def echo_task():
                return await client.query_server("echo", "Hello from stdio")

            async def sse_task():
                return await client.query_server("sse-client", "Hello from SSE")

            async def http_task():
                return await client.query_server("streamable-http-client", "Hello from HTTP")

            # Run all queries concurrently
            echo_result, sse_result, http_result = await asyncio.gather(
                echo_task(), sse_task(), http_task()
            )

            # Verify all results are correct
            self._assert_response_contains(echo_result, "ECHO: Hello from stdio")
            self._assert_response_contains(sse_result, "SSE: Hello from SSE")
            self._assert_response_contains(http_result, "HTTP: Hello from HTTP")
        
        except Exception as e:
            pytest.fail(f"Multiple clients test failed: {e}")
        finally:
            # Clean up
            await client.stop_server("echo")
            await client.stop_server("sse-server")
            await client.stop_server("streamable-http-server")
    
    @pytest.mark.asyncio
    async def test_server_restart_recovery(self, client):
        """Test that clients can reconnect when servers crash and restart."""
        # Use the echo server instead of WebSocket for this test
        await client.launch_server("echo")
        await asyncio.sleep(2)

        try:
            # First connection and query
            echo_client = await client.connect("echo")
            response1 = await client.query_server("echo", "First message")
            self._assert_response_contains(response1, "ECHO: First message")
            
            # Get the server PID
            server_name = "echo"
            if server_name in client._local_processes:
                process = client._local_processes[server_name]
                pid = process.pid

                # Force kill the server (simulating a crash)
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
                else:
                    os.kill(pid, signal.SIGKILL)

                # Give it time to die
                await asyncio.sleep(2)

                # Verify it's no longer running
                running, _ = client._is_server_running(server_name)
                assert not running

                # Restart the server
                await client.launch_server(server_name)
                await asyncio.sleep(2)

                # Try connecting and querying again
                echo_client2 = await client.connect("echo")
                response2 = await client.query_server("echo", "After restart")
                self._assert_response_contains(response2, "ECHO: After restart")
            else:
                pytest.skip("Could not find server process to test restart recovery")
                
        except Exception as e:
            pytest.fail(f"Server restart recovery test failed: {e}")
        finally:
            # Clean up
            await client.stop_server("echo")