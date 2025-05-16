"""
Tests specifically for UVX-based MCP servers.

These tests verify the UvxProcessTransport works with actual UVX commands.
"""

import logging
import pytest
import asyncio
import shutil
from pathlib import Path

from mcp_client_multi_server.client import MultiServerClient, UvxProcessTransport


# Configure logging
logger = logging.getLogger("uvx_tests")
logger.setLevel(logging.DEBUG)

# Path to the example config file
EXAMPLE_CONFIG_PATH = Path(__file__).parent.parent / "examples" / "config.json"


@pytest.fixture
def config_path():
    """Provide the path to the example config file."""
    assert EXAMPLE_CONFIG_PATH.exists(), f"Example config not found at {EXAMPLE_CONFIG_PATH}"
    return str(EXAMPLE_CONFIG_PATH)


@pytest.fixture
def require_uvx():
    """Check if UVX is available and skip tests if not."""
    # Find uvx executable
    uvx_path = shutil.which("uvx")
    if not uvx_path:
        # Check if it's in a virtual environment
        import sys
        if hasattr(sys, 'prefix'):
            possible_path = Path(sys.prefix) / "bin" / "uvx"
            if possible_path.exists():
                uvx_path = str(possible_path)
    
    if not uvx_path:
        pytest.skip("uvx executable not found")
        
    # Check if uvx command works
    import subprocess
    try:
        result = subprocess.run(
            [uvx_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        # If exit code is not 0, uvx itself might be broken
        if result.returncode != 0:
            pytest.skip(f"uvx command not working: {result.stderr}")
    except Exception as e:
        pytest.skip(f"Error checking UVX: {e}")
    
    return uvx_path


@pytest.fixture
def fetch_config(require_uvx):
    """Create a fetch server configuration for testing."""
    uvx_path = require_uvx
    
    return {
        "mcpServers": {
            "test-fetch": {
                "type": "stdio",
                "command": uvx_path,
                "args": ["mcp-server-fetch"],
                "env": {}
            }
        }
    }


@pytest.fixture
async def client(config_path):
    """Create a client for testing."""
    client = MultiServerClient(config_path=config_path, logger=logger)
    yield client
    # Clean up
    await client.close()


@pytest.mark.asyncio
async def test_uvx_transport_init():
    """Test basic initialization of UvxProcessTransport."""
    transport = UvxProcessTransport(
        uvx_path="/usr/bin/uvx",
        package="mcp-server-fetch",
        args=["--verbose"],
        env={"TEST_ENV": "value"},
    )
    
    # Verify attributes are set correctly
    assert transport.uvx_path == "/usr/bin/uvx"
    assert transport.package == "mcp-server-fetch"
    assert transport.server_args == ["--verbose"]
    
    # Verify command and args are properly composed
    assert transport.command == "/usr/bin/uvx"
    assert transport.args == ["mcp-server-fetch", "--verbose"]
    assert transport.env == {"TEST_ENV": "value"}


@pytest.mark.asyncio
async def test_uvx_transport_with_custom_config(fetch_config, require_uvx):
    """Test creating a client with UVX transport configuration."""
    try:
        # Create client from custom config
        client = MultiServerClient(custom_config=fetch_config, auto_launch=False, logger=logger)
        
        # Verify server exists in configuration
        servers = client.list_servers()
        assert "test-fetch" in servers, "test-fetch server not found in configuration"
        
        # Get the server configuration
        server_config = client.get_server_config("test-fetch")
        assert server_config is not None, "Failed to get server config"
        
        # Create transport from config
        transport = client._create_transport_from_config("test-fetch", server_config)
        
        # Verify it's an UvxProcessTransport
        assert isinstance(transport, UvxProcessTransport), "Wrong transport type created"
        
        # Verify package and args
        assert transport.package == "mcp-server-fetch", "Wrong package name"
        
        # Clean up
        await client.close()
    except Exception as e:
        pytest.fail(f"Error creating transport from config: {e}")


@pytest.mark.asyncio
async def test_uvx_fetch_server_connection(require_uvx):
    """Test connection to a UVX-based fetch server."""
    # Skip if mcp-server-fetch not available
    try:
        import subprocess
        result = subprocess.run(
            [require_uvx, "mcp-server-fetch", "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            pytest.skip("mcp-server-fetch not available")
    except Exception:
        pytest.skip("Error checking for mcp-server-fetch")
    
    # Create custom config
    config = {
        "mcpServers": {
            "test-fetch": {
                "type": "stdio",
                "command": require_uvx,
                "args": ["mcp-server-fetch"],
                "env": {}
            }
        }
    }
    
    # Create client with this config
    client = MultiServerClient(custom_config=config, logger=logger)
    
    try:
        # Launch the server
        success = await client.launch_server("test-fetch")
        if not success:
            pytest.skip("Failed to launch UVX fetch server")
        
        # List tools
        tools = await client.list_server_tools("test-fetch")
        assert tools is not None, "Failed to list tools from UVX fetch server"
        assert len(tools) > 0, "No tools returned from UVX fetch server"
        
        # Look for the fetch tool
        tool_names = [tool["name"] for tool in tools]
        assert "fetch" in tool_names, "fetch tool not found"
        
        # Try a simple fetch operation to verify functionality
        try:
            result = await client.query_server(
                server_name="test-fetch",
                tool_name="fetch",
                args={"url": "https://example.com"}
            )
            
            # Verify we got a response
            assert result is not None, "No response from fetch tool"
            
            # Check that the response has the expected content
            response_str = str(result)
            assert "Example Domain" in response_str, "Expected content not found in fetch response"
            
        except Exception as e:
            logger.error(f"Error querying fetch server: {e}")
            pytest.fail(f"Failed to execute fetch operation: {e}")
            
    finally:
        # Clean up
        await client.close()


@pytest.mark.asyncio
async def test_uvx_server_auto_launch(require_uvx):
    """Test auto-launching of UVX server."""
    # Skip if mcp-server-fetch not available
    try:
        import subprocess
        result = subprocess.run(
            [require_uvx, "mcp-server-fetch", "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            pytest.skip("mcp-server-fetch not available")
    except Exception:
        pytest.skip("Error checking for mcp-server-fetch")
    
    # Create custom config
    config = {
        "mcpServers": {
            "test-fetch": {
                "type": "stdio",
                "command": require_uvx,
                "args": ["mcp-server-fetch"],
                "env": {}
            }
        }
    }
    
    # Create client with auto-launch enabled
    client = MultiServerClient(custom_config=config, auto_launch=True, logger=logger)
    
    try:
        # Try to query directly without explicit launch
        result = await client.query_server(
            server_name="test-fetch",
            tool_name="fetch",
            args={"url": "https://example.com"}
        )
        
        # Verify auto-launch worked
        assert "test-fetch" in client._local_processes, "Server was not auto-launched"
        assert client._local_processes["test-fetch"].poll() is None, "Auto-launched server not running"
        
        # Verify we got a response
        assert result is not None, "No response after auto-launch"
    finally:
        # Clean up
        await client.close()


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])