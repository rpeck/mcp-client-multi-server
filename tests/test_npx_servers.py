"""
Tests specifically for NPX-based MCP servers.
"""

import logging
import pytest
import asyncio
from pathlib import Path

from mcp_client_multi_server.client import MultiServerClient

# Path to the example config file
EXAMPLE_CONFIG_PATH = Path(__file__).parent.parent / "examples" / "config.json"

# Configure logging
logger = logging.getLogger("npx_tests")
logger.setLevel(logging.DEBUG)


@pytest.fixture
def config_path():
    """Provide the path to the example config file."""
    assert EXAMPLE_CONFIG_PATH.exists(), f"Example config not found at {EXAMPLE_CONFIG_PATH}"
    return str(EXAMPLE_CONFIG_PATH)


@pytest.fixture
def require_npx_filesystem():
    """
    Check if the NPX filesystem package is available.
    Skip tests if it's not available.
    """
    import subprocess
    import shutil

    # Find npx executable
    npx_path = shutil.which("npx")
    if not npx_path:
        pytest.skip("npx executable not found")

    # Check if the filesystem package is available
    try:
        # Run a simple check command that doesn't actually run the server
        result = subprocess.run(
            [npx_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        # If exit code is not 0, npx itself might be broken
        if result.returncode != 0:
            pytest.skip(f"npx command not working: {result.stderr}")

        # Now specifically check the filesystem package
        # We can check if it's installed globally first
        result = subprocess.run(
            ["npm", "list", "-g", "@modelcontextprotocol/server-filesystem"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # If not globally installed, we'll fall back to npx's on-demand behavior
        if "empty" in result.stdout or "@modelcontextprotocol/server-filesystem" not in result.stdout:
            # The package is not globally installed, but we can still try with npx directly
            logger.info("Filesystem package not found in global npm packages, will try on-demand with npx")
    except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        pytest.skip(f"Error checking for NPX or filesystem package: {e}")

    # If we get here, either the package is installed or we'll let npx try to install it on-demand
    return npx_path


@pytest.fixture
async def client(config_path):
    """Create a MultiServerClient instance for testing."""
    client = MultiServerClient(config_path=config_path, logger=logger)
    yield client
    # Clean up after tests
    await client.close()


@pytest.mark.asyncio
async def test_filesystem_server_launch(require_npx_filesystem):
    """Test launching the filesystem server directly."""
    logger.info("Creating client for launch test")
    client = MultiServerClient(config_path=str(EXAMPLE_CONFIG_PATH), logger=logger)

    try:
        # Launch server directly
        logger.info("Attempting to launch filesystem server")
        launch_result = await client.launch_server("filesystem")

        # Verify launch
        assert launch_result is True, "Failed to launch filesystem server"
        assert "filesystem" in client._local_processes, "Server process not found"
        assert client._local_processes["filesystem"].poll() is None, "Server process not running"

        # Wait a moment to let server initialize
        await asyncio.sleep(1)

        # Verify server is running by checking its PID
        pid = client._local_processes["filesystem"].pid
        assert pid > 0, "Invalid process ID"
        logger.info(f"Filesystem server running with PID: {pid}")

    finally:
        # Always clean up
        logger.info("Cleaning up client")
        await client.close()


@pytest.mark.asyncio
async def test_filesystem_server_tools(require_npx_filesystem):
    """Test listing tools from the filesystem server."""
    logger.info("Creating client for tools test")
    client = MultiServerClient(config_path=str(EXAMPLE_CONFIG_PATH), logger=logger)

    try:
        # Launch and connect
        await client.launch_server("filesystem")

        # List tools directly
        logger.info("Listing tools from filesystem server")
        tools = await client.list_server_tools("filesystem")

        # Verify tools
        assert tools is not None, "No tools returned"
        assert len(tools) > 0, "Empty tools list returned"

        # Check for expected tools
        tool_names = [tool["name"] for tool in tools]
        logger.info(f"Found tools: {tool_names}")

        # Filesystem server should have specific tools
        expected_tools = ["list_directory", "read_file", "write_file", "list_allowed_directories"]
        for expected_tool in expected_tools:
            assert any(expected_tool in name for name in tool_names), \
                   f"Expected tool not found: {expected_tool}"

    finally:
        # Clean up
        logger.info("Cleaning up client")
        await client.close()


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])