"""
Tests for server lifecycle management.

These tests verify the proper functionality of the MultiServerClient's
server lifecycle management features, including:

1. Transport-specific server identification
2. Proper server stopping behavior based on server type
3. Server registry functionality
4. Process tracking and detachment
5. Persistence control via API parameters
"""

import asyncio
import pytest
import logging
import sys
import os
import time
import tempfile
import shutil
import json
from pathlib import Path
from typing import Dict, Optional, List, Tuple

from mcp_client_multi_server.client import MultiServerClient, ServerInfo

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_server_lifecycle")


@pytest.fixture
def config_path():
    """Fixture to provide the config path."""
    path = Path("examples/config.json")
    if not path.exists():
        pytest.skip("Configuration file not found")
    return path


@pytest.fixture
async def client(config_path):
    """Fixture to provide a client instance."""
    client = MultiServerClient(config_path=config_path, logger=logger)
    yield client
    # Clean up any remaining servers after tests
    await client.stop_all_servers()


@pytest.fixture
def temp_registry_dir():
    """Fixture to provide a temporary directory for the server registry."""
    # Create a temporary directory for the registry
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Clean up after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_server_identification(client):
    """
    Test server type identification logic.

    This test verifies that the client correctly identifies different types of servers:
    1. Local STDIO servers (rely on stdin/stdout pipes)
    2. URL-based servers (never identified as local STDIO)
    3. Socket-based servers (planned for future - currently identified by URL presence)
    """
    servers = client.list_servers()
    assert len(servers) > 0, "No servers found in configuration"

    stdio_servers = []
    url_servers = []

    # Test if servers are properly identified
    for server in servers:
        config = client.get_server_config(server)
        server_type = config.get("type", "unknown")

        # Track server by type for additional assertions
        if "url" in config:
            url_servers.append(server)
        elif server_type == "stdio":
            stdio_servers.append(server)

        # All stdio servers in our test config should be identified as STDIO servers
        if server_type == "stdio" and "url" not in config:
            assert client._is_local_stdio_server(server), f"Server {server} should be identified as a local STDIO server"

        # URL-based servers should never be identified as STDIO servers
        if "url" in config:
            assert not client._is_local_stdio_server(server), f"Server {server} with URL should not be identified as a local STDIO server"

    # Verify we have at least one STDIO server in our test config
    assert len(stdio_servers) > 0, "No STDIO servers found in configuration, tests will be incomplete"

    # Test behavior with servers that don't exist in config
    assert not client._is_local_stdio_server("non-existent-server"), \
        "Non-existent servers should not be identified as local STDIO servers"

    # Test behavior with mocked server configurations
    # Create a temporary config entry with URL for testing
    if 'echo' in stdio_servers:
        original_config = client.get_server_config('echo')
        try:
            # Temporarily modify the config to test URL detection
            url_config = original_config.copy()
            url_config['url'] = 'http://localhost:8080'
            client._config['mcpServers']['echo-with-url'] = url_config

            # Verify URL-based server is not identified as STDIO
            assert not client._is_local_stdio_server('echo-with-url'), \
                "Server with URL should not be identified as local STDIO server"
        finally:
            # Clean up
            if 'echo-with-url' in client._config.get('mcpServers', {}):
                del client._config['mcpServers']['echo-with-url']


@pytest.mark.asyncio
async def test_server_launch_and_close(client, config_path):
    """
    Test server launch and close behavior with automatic stopping.

    This test verifies:
    1. Servers can be successfully launched
    2. Server processes are tracked correctly
    3. Server registry is updated with running server info
    4. When client closes with stop_servers=True, STDIO servers are stopped
    """
    servers = client.list_servers()

    # Find first launchable server
    launchable_server = None
    for server in servers:
        config = client.get_server_config(server)
        if client._is_launchable(config):
            launchable_server = server
            break

    if not launchable_server:
        pytest.skip("No launchable servers found in config")

    # Launch the server
    success = await client.launch_server(launchable_server)
    assert success, f"Failed to launch server {launchable_server}"

    # Verify running status
    running, pid = client._is_server_running(launchable_server)
    assert running, f"Server {launchable_server} should be running"
    assert pid is not None, "Server PID should not be None"

    # Verify server is in registry
    assert launchable_server in client._server_registry, "Server should be in registry"
    assert client._server_registry[launchable_server].pid == pid, "PID in registry should match"

    # Verify log files exist
    assert client._server_registry[launchable_server].stdout_log is not None, "stdout log path should exist"
    assert client._server_registry[launchable_server].stderr_log is not None, "stderr log path should exist"
    assert client._server_registry[launchable_server].stdout_log.exists(), "stdout log file should exist"
    assert client._server_registry[launchable_server].stderr_log.exists(), "stderr log file should exist"

    # Verify STDIO identification
    assert client._is_local_stdio_server(launchable_server), f"Server {launchable_server} should be identified as a local STDIO server"

    # Verify it's in the local processes tracking
    assert launchable_server in client._local_processes, "Server should be in local processes"

    # Test closing with stop_servers=True (default behavior for query operations)
    await client.close(stop_servers=True)

    # Check if server was stopped
    running, pid = client._is_server_running(launchable_server)
    assert not running, f"Server {launchable_server} should be stopped after closing with stop_servers=True"

    # Verify it's no longer in local processes
    assert launchable_server not in client._local_processes, "Server should be removed from local processes"


@pytest.mark.asyncio
async def test_selective_stopping_behavior(client):
    """
    Test that the client's transport-specific server stopping logic works correctly.

    This test verifies:
    1. The stop_local_stdio_servers method only stops STDIO servers
    2. Socket-based and remote servers are never automatically stopped
    3. The close() method respects the server type when determining what to stop
    4. The stop_all_servers method works correctly to stop all servers

    This is implemented using mock servers and methods to avoid actual process creation.
    """
    # Get list of servers
    servers = client.list_servers()
    assert len(servers) > 0, "No servers found in configuration"

    # Set up mock servers of different types
    mock_stdio_server = "mock-stdio-server"        # Standard local stdio server
    mock_non_stdio_server = "mock-non-stdio-server"  # Non-stdio server (socket-based)
    mock_url_server = "mock-url-server"            # URL-based remote server

    # Create a mock process object that appears to be running
    class MockProcess:
        def __init__(self, pid):
            self.pid = pid
            self._stdout_file = None
            self._stderr_file = None
            self._stdout_path = Path("/tmp/mock_stdout.log")
            self._stderr_path = Path("/tmp/mock_stderr.log")

        def poll(self):
            return None  # Indicate the process is still running

    # Add mock server data to structures
    client._local_processes[mock_stdio_server] = MockProcess(999999)
    client._local_processes[mock_non_stdio_server] = MockProcess(999998)
    client._launched_servers.add(mock_stdio_server)
    client._launched_servers.add(mock_non_stdio_server)

    # Add servers to registry
    client._server_registry[mock_stdio_server] = ServerInfo(
        server_name=mock_stdio_server,
        pid=999999,
        start_time=time.time(),
        config_hash="abc123",
        log_dir=Path("/tmp"),
        stdout_log=Path("/tmp/mock_stdout.log"),
        stderr_log=Path("/tmp/mock_stderr.log")
    )

    client._server_registry[mock_non_stdio_server] = ServerInfo(
        server_name=mock_non_stdio_server,
        pid=999998,
        start_time=time.time(),
        config_hash="def456",
        log_dir=Path("/tmp"),
        stdout_log=Path("/tmp/mock_stdout2.log"),
        stderr_log=Path("/tmp/mock_stderr2.log")
    )

    # Add URL-based server to config
    client._config["mcpServers"][mock_url_server] = {
        "url": "http://localhost:8080",
        "type": "http"
    }

    # Override _is_local_stdio_server to provide deterministic results
    original_is_local_stdio_server = client._is_local_stdio_server

    def test_is_local_stdio_server(server_name):
        if server_name == mock_stdio_server:
            return True
        if server_name == mock_non_stdio_server or server_name == mock_url_server:
            return False
        return original_is_local_stdio_server(server_name)

    # Track which servers were stopped
    stopped_servers = []

    # Mock stop_server to avoid actual process stopping but track calls
    original_stop_server = client.stop_server

    async def mock_stop_server(server_name):
        stopped_servers.append(server_name)
        # Simulate successful stop by removing from local processes
        if server_name in client._local_processes:
            del client._local_processes[server_name]
        if server_name in client._server_registry:
            del client._server_registry[server_name]
        return True

    try:
        # Apply monkey patches
        client._is_local_stdio_server = test_is_local_stdio_server
        client.stop_server = mock_stop_server

        # TEST 1: stop_local_stdio_servers should only stop STDIO servers
        stopped_servers.clear()
        await client.stop_local_stdio_servers()

        assert mock_stdio_server in stopped_servers, \
            "stop_local_stdio_servers should stop STDIO servers"
        assert mock_non_stdio_server not in stopped_servers, \
            "stop_local_stdio_servers should NOT stop non-STDIO servers"
        assert mock_url_server not in stopped_servers, \
            "stop_local_stdio_servers should NOT stop URL-based servers"

        # Reset for next test
        stopped_servers.clear()
        client._local_processes[mock_stdio_server] = MockProcess(999999)
        client._local_processes[mock_non_stdio_server] = MockProcess(999998)
        client._server_registry[mock_stdio_server] = ServerInfo(
            server_name=mock_stdio_server, pid=999999)
        client._server_registry[mock_non_stdio_server] = ServerInfo(
            server_name=mock_non_stdio_server, pid=999998)

        # TEST 2: close() with stop_servers=True should only stop STDIO servers
        await client.close(stop_servers=True)

        assert mock_stdio_server in stopped_servers, \
            "close(stop_servers=True) should stop STDIO servers"
        assert mock_non_stdio_server not in stopped_servers, \
            "close(stop_servers=True) should NOT stop non-STDIO servers"
        assert mock_url_server not in stopped_servers, \
            "close(stop_servers=True) should NOT stop URL-based servers"

        # Reset for next test
        stopped_servers.clear()
        client._local_processes[mock_stdio_server] = MockProcess(999999)
        client._local_processes[mock_non_stdio_server] = MockProcess(999998)
        client._server_registry[mock_stdio_server] = ServerInfo(
            server_name=mock_stdio_server, pid=999999)
        client._server_registry[mock_non_stdio_server] = ServerInfo(
            server_name=mock_non_stdio_server, pid=999998)

        # TEST 3: close() with stop_servers=False should not stop any servers
        await client.close(stop_servers=False)

        assert len(stopped_servers) == 0, \
            "close(stop_servers=False) should not stop any servers"

        # Reset for next test
        stopped_servers.clear()
        client._local_processes[mock_stdio_server] = MockProcess(999999)
        client._local_processes[mock_non_stdio_server] = MockProcess(999998)
        client._server_registry[mock_stdio_server] = ServerInfo(
            server_name=mock_stdio_server, pid=999999)
        client._server_registry[mock_non_stdio_server] = ServerInfo(
            server_name=mock_non_stdio_server, pid=999998)

        # TEST 4: stop_all_servers should stop all known servers
        await client.stop_all_servers()

        assert mock_stdio_server in stopped_servers, \
            "stop_all_servers should stop STDIO servers"
        assert mock_non_stdio_server in stopped_servers, \
            "stop_all_servers should stop non-STDIO servers"
        # URL servers are not in local_processes or registry, so they won't be stopped

    finally:
        # Clean up and restore original methods
        client._is_local_stdio_server = original_is_local_stdio_server
        client.stop_server = original_stop_server

        # Remove mock servers from client structures
        for server in [mock_stdio_server, mock_non_stdio_server, mock_url_server]:
            if server in client._local_processes:
                del client._local_processes[server]
            if server in client._launched_servers:
                client._launched_servers.remove(server)
            if server in client._server_registry:
                del client._server_registry[server]
            if server in client._config.get("mcpServers", {}):
                del client._config["mcpServers"][server]


@pytest.mark.asyncio
async def test_server_registry_persistence(config_path, temp_registry_dir):
    """
    Test the persistence of server registry between client instances.

    This test verifies:
    1. Server info is saved to registry when a server is launched
    2. Registry is loaded when a new client instance is created
    3. Running servers can be detected across client instances
    4. Servers don't need to be relaunched if already running
    """
    # Monkeypatch the SERVER_TRACKING_DIR and SERVER_REGISTRY_FILE for the test
    original_tracking_dir = MultiServerClient.SERVER_TRACKING_DIR
    original_registry_file = MultiServerClient.SERVER_REGISTRY_FILE
    original_log_dir = MultiServerClient.LOG_DIR

    # Create custom paths for this test
    MultiServerClient.SERVER_TRACKING_DIR = temp_registry_dir
    MultiServerClient.SERVER_REGISTRY_FILE = temp_registry_dir / "servers.json"
    MultiServerClient.LOG_DIR = temp_registry_dir / "logs"

    try:
        # Create client 1
        client1 = MultiServerClient(config_path=config_path, logger=logger)

        # Set up a mock server with a fake PID that we'll pretend is running
        mock_server_name = "mock-persistent-server"
        mock_pid = 999997

        # Add the server to the registry with ServerInfo
        client1._server_registry[mock_server_name] = ServerInfo(
            server_name=mock_server_name,
            pid=mock_pid,
            start_time=time.time(),
            config_hash="abc123",
            log_dir=temp_registry_dir / "logs",
            stdout_log=temp_registry_dir / "logs" / f"{mock_server_name}_stdout.log",
            stderr_log=temp_registry_dir / "logs" / f"{mock_server_name}_stderr.log"
        )

        # Save the registry to disk
        client1._save_server_registry()

        # Verify registry file was created
        assert MultiServerClient.SERVER_REGISTRY_FILE.exists(), \
            "Registry file should have been created"

        # Monkey-patch the _is_server_running method to recognize our mock PID as running
        def mock_is_server_running(self, server_name):
            """Mocked method that pretends our mock server is running."""
            if server_name == mock_server_name:
                return True, mock_pid
            # Call original method for other servers
            original_method = original_is_server_running
            return original_method(self, server_name)

        # Save original method
        original_is_server_running = MultiServerClient._is_server_running

        # Apply the patch to the class
        MultiServerClient._is_server_running = mock_is_server_running

        # Create client 2 that should load the registry from disk
        client2 = MultiServerClient(config_path=config_path, logger=logger)

        # Verify client2 loaded the registry
        assert mock_server_name in client2._server_registry, \
            "Client 2 should have loaded the server from registry"

        # Verify correct data was loaded
        registry_entry = client2._server_registry[mock_server_name]
        assert registry_entry.pid == mock_pid, \
            "PID in loaded registry should match what was saved"

        # Check if client2 can detect the server is running
        is_running, pid = client2._is_server_running(mock_server_name)
        assert is_running, "Client 2 should detect server is running via registry"
        assert pid == mock_pid, "PID returned from is_running should match registry"

        # Clean up
        await client1.close(stop_servers=False)
        await client2.close(stop_servers=False)

    finally:
        # Restore the original class attributes and methods
        MultiServerClient.SERVER_TRACKING_DIR = original_tracking_dir
        MultiServerClient.SERVER_REGISTRY_FILE = original_registry_file
        MultiServerClient.LOG_DIR = original_log_dir
        MultiServerClient._is_server_running = original_is_server_running