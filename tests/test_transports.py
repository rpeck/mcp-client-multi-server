import pytest
import os
import sys
import shutil
import asyncio
from pathlib import Path

from mcp_client_multi_server.client import (
    MultiServerClient,
    NpxProcessTransport,
    UvxProcessTransport,
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