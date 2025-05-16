import pytest
import os
import sys
import shutil
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastmcp.client.transports import (
    WSTransport,
    SSETransport,
    StreamableHttpTransport
)

from mcp_client_multi_server.client import (
    MultiServerClient,
    NpxProcessTransport,
    UvxProcessTransport,
    WebSocketConfig,
    StreamableHttpConfig,
)


class TestTransports:
    def test_npx_process_transport_init(self):
        """Test initialization of NpxProcessTransport"""
        transport = NpxProcessTransport(
            npx_path="/usr/bin/npx",
            package="test-package",
            args=["--arg1", "--arg2"],
            env={"TEST_ENV": "value"},
        )
        
        # Check that attributes are correctly set
        assert transport.npx_path == "/usr/bin/npx"
        assert transport.package == "test-package"
        assert transport.server_args == ["--arg1", "--arg2"]
        
        # Check StdioTransport base class setup
        assert transport.command == "/usr/bin/npx"
        assert transport.args == ["-y", "test-package", "--arg1", "--arg2"]
        assert transport.env == {"TEST_ENV": "value"}

    def test_uvx_process_transport_init(self):
        """Test initialization of UvxProcessTransport"""
        transport = UvxProcessTransport(
            uvx_path="/usr/bin/uvx",
            package="test-package",
            args=["--arg1", "--arg2"],
            env={"TEST_ENV": "value"},
        )
        
        # Check that attributes are correctly set
        assert transport.uvx_path == "/usr/bin/uvx"
        assert transport.package == "test-package"
        assert transport.server_args == ["--arg1", "--arg2"]
        
        # Check StdioTransport base class setup
        assert transport.command == "/usr/bin/uvx"
        assert transport.args == ["test-package", "--arg1", "--arg2"]
        assert transport.env == {"TEST_ENV": "value"}

    @pytest.mark.asyncio
    async def test_transport_creation_from_config(self):
        """Test creation of transports from configuration with special handling"""
        # Skip direct testing of PythonStdioTransport and NodeStdioTransport as they require files

        # Create a test config
        config = {
            "mcpServers": {
                "npx-server": {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["test-package", "--arg1"],
                    "env": {"TEST_ENV": "value"}
                },
                "uvx-server": {
                    "type": "stdio",
                    "command": "uvx",
                    "args": ["test-package", "--arg1"],
                    "env": {"TEST_ENV": "value"}
                },
                "http-server": {
                    "url": "http://localhost:3000",
                    "env": {"TEST_ENV": "value"}
                }
            }
        }

        # Create client with custom config
        client = MultiServerClient(custom_config=config, auto_launch=False)

        # Test NpxProcessTransport creation
        npx_config = client.get_server_config("npx-server")
        transport = client._create_transport_from_config("npx-server", npx_config)
        assert isinstance(transport, NpxProcessTransport)
        assert transport.package == "test-package"
        assert "--arg1" in transport.args

        # Test UvxProcessTransport creation
        uvx_config = client.get_server_config("uvx-server")
        transport = client._create_transport_from_config("uvx-server", uvx_config)
        assert isinstance(transport, UvxProcessTransport)
        assert transport.package == "test-package"
        assert "--arg1" in transport.args

        # Test HTTP transport creation
        http_config = client.get_server_config("http-server")
        transport = client._create_transport_from_config("http-server", http_config)
        assert transport.url == "http://localhost:3000"

    @pytest.mark.asyncio
    async def test_websocket_advanced(self):
        """Test WebSocket transport configurations."""
        # Create a test config with WebSocket options
        config = {
            "mcpServers": {
                "ws-server": {
                    "url": "ws://localhost:8765/ws",
                    "ws_config": {
                        "ping_interval": 30.0,
                        "ping_timeout": 10.0,
                        "max_message_size": 1024 * 1024,  # 1MB
                        "compression": True
                    }
                },
                "ws-components-server": {
                    "type": "websocket",
                    "host": "example.com",
                    "port": 9000,
                    "path": "/mcp/ws",
                    "secure": True,  # Use wss://
                    "ws_config": {
                        "ping_interval": 45.0
                    }
                }
            }
        }

        # Create client with custom config
        client = MultiServerClient(custom_config=config, auto_launch=False)

        # Test WebSocket transport with config
        ws_config = client.get_server_config("ws-server")
        ws_transport = client._create_transport_from_config("ws-server", ws_config)
        assert isinstance(ws_transport, WSTransport)
        assert ws_transport.url == "ws://localhost:8765/ws"
        # Note: We can't test config parameters as WSTransport doesn't expose them

        # Test WebSocket from components
        ws_components_config = client.get_server_config("ws-components-server")
        ws_components_transport = client._create_transport_from_config("ws-components-server", ws_components_config)
        assert isinstance(ws_components_transport, WSTransport)
        assert ws_components_transport.url == "wss://example.com:9000/mcp/ws"

    @pytest.mark.asyncio
    async def test_sse_transport(self):
        """Test SSE transport creation."""
        # Create a test config with SSE options
        config = {
            "mcpServers": {
                "sse-server": {
                    "type": "sse",
                    "url": "https://example.com/mcp/sse"
                }
            }
        }

        # Create client with custom config
        client = MultiServerClient(custom_config=config, auto_launch=False)

        # Test SSE transport
        sse_config = client.get_server_config("sse-server")
        sse_transport = client._create_transport_from_config("sse-server", sse_config)
        assert isinstance(sse_transport, SSETransport)
        assert sse_transport.url == "https://example.com/mcp/sse"

    @pytest.mark.asyncio
    async def test_streamable_http_transport(self):
        """Test Streamable HTTP transport creation."""
        # Create a test config with Streamable HTTP options
        config = {
            "mcpServers": {
                "streamable-http-server": {
                    "url": "https://example.com/mcp/stream",
                    "http_config": {
                        "headers": {
                            "Authorization": "Bearer test-token",
                            "X-API-Key": "test-key"
                        }
                    }
                },
                "explicit-streamable-http": {
                    "type": "streamable-http",
                    "url": "https://example.com/api/stream",
                    "http_config": {
                        "headers": {
                            "Authorization": "Bearer explicit-token"
                        }
                    }
                }
            }
        }

        # Create client with custom config
        client = MultiServerClient(custom_config=config, auto_launch=False)

        # Test Streamable HTTP transport by URL pattern
        stream_http_config = client.get_server_config("streamable-http-server")
        stream_http_transport = client._create_transport_from_config("streamable-http-server", stream_http_config)
        assert isinstance(stream_http_transport, StreamableHttpTransport)
        assert stream_http_transport.url == "https://example.com/mcp/stream"
        # Note: We can't directly access headers attribute, FastMCP doesn't expose it

        # Test Streamable HTTP transport by explicit type
        explicit_stream_config = client.get_server_config("explicit-streamable-http")
        explicit_stream_transport = client._create_transport_from_config("explicit-streamable-http", explicit_stream_config)
        assert isinstance(explicit_stream_transport, StreamableHttpTransport)
        assert explicit_stream_transport.url == "https://example.com/api/stream"