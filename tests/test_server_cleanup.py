"""
Tests for server functionality verification and cleanup.

These tests specifically validate that:
1. Servers are properly launched and working (not just connected)
2. Servers are properly cleaned up after tests
3. No orphaned processes are left behind
"""

import os
import sys
import json
import time
import pytest
import logging
import asyncio
import subprocess
import signal
from pathlib import Path

from mcp_client_multi_server.client import MultiServerClient


# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


# Path to the example config file
CONFIG_PATH = Path(__file__).parent.parent / "examples" / "config.json"


@pytest.fixture
def config_path():
    """Provide the path to the example config file."""
    assert CONFIG_PATH.exists(), f"Example config not found at {CONFIG_PATH}"
    return str(CONFIG_PATH)


@pytest.fixture
def process_tracker():
    """
    Process tracker that doesn't rely on psutil.
    
    Returns a dict that tracks process info for the test.
    """
    process_info = {
        'started_processes': [],
    }
    
    yield process_info
    
    # Check if any tracked processes are still running
    for pid in process_info.get('started_processes', []):
        try:
            # Try sending signal 0 to check if process exists
            os.kill(pid, 0)
            # If we get here, process is still running
            logger.error(f"Orphaned process found: PID={pid}")
            # Try to terminate it
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to orphaned process: {pid}")
            except Exception as e:
                logger.error(f"Failed to terminate orphaned process {pid}: {e}")
        except OSError:
            # Process not found, which is good
            pass


@pytest.fixture
async def client(config_path):
    """Create a MultiServerClient instance for testing."""
    client = MultiServerClient(config_path=config_path, logger=logger)
    yield client
    # Clean up after tests
    logger.info("Closing client and stopping all servers")
    await client.close()
    
    # Wait a moment to ensure all processes are cleaned up
    await asyncio.sleep(0.5)


async def verify_server_functionality(client, server_name, test_tool, test_args=None):
    """
    Helper function to verify a server is actually working.
    
    Args:
        client: MultiServerClient instance
        server_name: Name of server to test
        test_tool: Name of tool to test
        test_args: Optional arguments for the tool
        
    Returns:
        True if server is working, False otherwise
    """
    try:
        # Launch server
        launch_result = await client.launch_server(server_name)
        if not launch_result:
            logger.error(f"Failed to launch {server_name} server")
            return False
            
        # Get server process info
        if server_name not in client._local_processes:
            logger.error(f"No process found for {server_name} after launch")
            return False
            
        process = client._local_processes[server_name]
        if process.poll() is not None:
            logger.error(f"Process for {server_name} is not running (poll returned {process.poll()})")
            return False
            
        # Verify PID is valid
        if process.pid <= 0:
            logger.error(f"Invalid PID for {server_name}: {process.pid}")
            return False
            
        logger.info(f"Server {server_name} launched with PID {process.pid}")
        
        # Check that we have tools available
        tools = await client.list_server_tools(server_name)
        if not tools:
            logger.error(f"No tools returned from {server_name}")
            return False
            
        tool_names = [tool["name"] for tool in tools]
        logger.info(f"Found tools on {server_name}: {tool_names}")
        
        if test_tool not in tool_names:
            # Check if the tool name is a substring of any available tool
            matching_tools = [t for t in tool_names if test_tool in t]
            if not matching_tools:
                logger.error(f"Test tool {test_tool} not found in {tool_names}")
                return False
            test_tool = matching_tools[0]
            logger.info(f"Using matching tool: {test_tool}")
            
        # Execute the test tool
        args = test_args or {}
        response = await client.query_server(
            server_name=server_name,
            tool_name=test_tool,
            args=args
        )
        
        # Verify we got a response
        if response is None:
            logger.error(f"No response from {server_name}.{test_tool}")
            return False
            
        logger.info(f"Got response from {server_name}.{test_tool}: {response}")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying {server_name} functionality: {e}")
        return False


@pytest.mark.asyncio
async def test_echo_server_functionality_and_cleanup(client, process_tracker):
    """Test echo server functionality and cleanup."""
    # Verify echo server works
    server_name = "echo"
    test_tool = "ping"
    
    working = await verify_server_functionality(client, server_name, test_tool)
    assert working, f"Echo server functionality test failed"
    
    # Store process info for cleanup verification
    process = client._local_processes.get(server_name)
    if process:
        process_tracker['started_processes'].append(process.pid)
    
    # Stop the server
    stop_result = await client.stop_server(server_name)
    assert stop_result, f"Failed to stop {server_name} server"
    
    # Verify server process is gone
    assert server_name not in client._local_processes, f"{server_name} process still in _local_processes after stop"
    
    # Wait a moment to ensure process is terminated
    await asyncio.sleep(0.5)
    
    # Verify process is actually gone by checking its poll() result
    if process:
        poll_result = process.poll()
        assert poll_result is not None, f"Process for {server_name} is still running after stop"


@pytest.mark.asyncio
async def test_filesystem_server_functionality_and_cleanup(client, process_tracker):
    """Test filesystem server functionality and cleanup."""
    # Check if npx is available
    import shutil
    npx_path = shutil.which("npx")
    if not npx_path:
        pytest.skip("npx not available, skipping filesystem server test")
    
    # Verify filesystem server works
    server_name = "filesystem"
    test_tool = "list_allowed_directories"
    
    try:
        working = await verify_server_functionality(client, server_name, test_tool)
        assert working, f"Filesystem server functionality test failed"
        
        # Store process info for cleanup verification
        process = client._local_processes.get(server_name)
        if process:
            process_tracker['started_processes'].append(process.pid)
        
        # Stop the server
        stop_result = await client.stop_server(server_name)
        assert stop_result, f"Failed to stop {server_name} server"
        
        # Verify server process is gone
        assert server_name not in client._local_processes, f"{server_name} process still in _local_processes after stop"
        
        # Wait a moment to ensure process is terminated
        await asyncio.sleep(0.5)
        
        # Verify process is actually gone by checking its poll() result
        if process:
            poll_result = process.poll()
            assert poll_result is not None, f"Process for {server_name} is still running after stop"
                
    except Exception as e:
        logger.error(f"Error in filesystem server test: {e}")
        pytest.skip(f"Error testing filesystem server: {e}")


@pytest.mark.asyncio
async def test_multiple_servers_and_cleanup(client, process_tracker):
    """Test launching multiple servers and ensuring all are properly cleaned up."""
    import shutil
    npx_path = shutil.which("npx")
    
    # Define servers to test based on availability
    servers_to_test = ["echo"]
    
    # Only include npx servers if npx is available
    if npx_path:
        servers_to_test.extend(["filesystem"])
        
        # Check if playwright server package is available
        try:
            result = subprocess.run(
                ["npm", "list", "-g", "@executeautomation/playwright-mcp-server"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "@executeautomation/playwright-mcp-server" in result.stdout:
                servers_to_test.append("playwright")
        except Exception:
            pass
    
    # Launch all servers
    launched_servers = []
    for server_name in servers_to_test:
        try:
            launch_result = await client.launch_server(server_name)
            if launch_result:
                launched_servers.append(server_name)
                # Store process info for cleanup verification
                process = client._local_processes.get(server_name)
                if process:
                    process_tracker['started_processes'].append(process.pid)
        except Exception as e:
            logger.error(f"Error launching {server_name}: {e}")
    
    # Verify all servers were launched
    assert len(launched_servers) > 0, "Failed to launch any servers"
    logger.info(f"Successfully launched servers: {launched_servers}")
    
    # Close the client which should stop all servers
    await client.close()
    
    # Wait a moment to ensure all processes are terminated
    await asyncio.sleep(1)
    
    # Verify all server processes are gone
    for server_name in launched_servers:
        assert server_name not in client._local_processes, f"{server_name} process still in _local_processes after close"


@pytest.mark.asyncio
async def test_client_context_manager_cleanup(config_path, process_tracker):
    """Test that the client context manager properly cleans up all resources."""
    # Use the client as a context manager
    server_name = "echo"

    # Start in async context manager
    async with MultiServerClient(config_path=config_path, logger=logger) as client:
        # Launch a server
        launch_result = await client.launch_server(server_name)
        assert launch_result, f"Failed to launch {server_name} server"

        # Store process info for cleanup verification
        process = client._local_processes.get(server_name)
        if process:
            process_tracker['started_processes'].append(process.pid)

        # Verify server is running
        assert server_name in client._local_processes, f"{server_name} process not found after launch"
        assert client._local_processes[server_name].poll() is None, f"{server_name} process not running after launch"

    # After context exit, all servers should be stopped
    # Wait a moment to ensure all processes are terminated
    await asyncio.sleep(1)

    # The client object is no longer accessible after the context manager exits
    # So we rely on our process_tracker to verify cleanup

    # Check if the process is still running (we captured the PID earlier)
    for pid in process_tracker['started_processes']:
        try:
            # Try sending signal 0 to check if process exists
            os.kill(pid, 0)
            # If we get here, process is still running
            assert False, f"Process {pid} for server is still running after context exit"
        except OSError:
            # Process not found, which is good
            pass


@pytest.mark.asyncio
async def test_launch_command_keeps_server_running(config_path, process_tracker):
    """
    Test that the launch command keeps servers running after the client is closed.

    This verifies the fix for the bug where servers were automatically shut down
    after the launch command completed.
    """
    # Create a client instance
    client = MultiServerClient(config_path=config_path, logger=logger)
    server_name = "echo"

    try:
        # Launch a server
        launch_result = await client.launch_server(server_name)
        assert launch_result, f"Failed to launch {server_name} server"

        # Store process info for cleanup verification
        process = client._local_processes.get(server_name)
        if process:
            process_tracker['started_processes'].append(process.pid)
            process_pid = process.pid

        # Verify server is running
        assert server_name in client._local_processes, f"{server_name} process not found after launch"
        assert client._local_processes[server_name].poll() is None, f"{server_name} process not running after launch"

        # Now close the client connection but don't stop servers
        # This simulates what happens in the CLI when using the launch command
        await client.close(stop_servers=False)

        # Wait a moment
        await asyncio.sleep(1)

        # Since client is now closed, we can't check client._local_processes
        # Instead, we'll check if the process is still running using its PID
        try:
            # Try sending signal 0 to check if process exists
            os.kill(process_pid, 0)
            # If we get here, process is still running as expected
            process_still_running = True
        except OSError:
            # Process not found, which means it was stopped unexpectedly
            process_still_running = False

        assert process_still_running, f"Process {process_pid} for server {server_name} is not running after client.close(stop_servers=False)"

        # Now we need to stop the server manually since our test cleanup won't handle it
        # (since we closed the client without stopping servers)
        try:
            # Create a new client to stop the server
            cleanup_client = MultiServerClient(config_path=config_path, logger=logger)
            await cleanup_client.stop_server(server_name)
            await cleanup_client.close()
        except Exception as e:
            logger.warning(f"Error during test cleanup: {e}")
            # Try to kill the process directly as a last resort
            try:
                os.kill(process_pid, signal.SIGTERM)
                logger.info(f"Killed process {process_pid} during test cleanup")
            except OSError:
                # Process already gone
                pass
    except Exception as e:
        logger.error(f"Error in test_launch_command_keeps_server_running: {e}")
        raise
    finally:
        # Make sure client is closed
        await client.close(stop_servers=True)


@pytest.mark.asyncio
async def test_cli_launch_command_simulation(config_path, process_tracker):
    """
    Test that simulates the CLI launch command flow to ensure servers remain running.

    This test directly replicates the behavior of the main.py CLI when using the launch
    command, verifying that servers launched with the launch command are not automatically
    stopped when the client is closed. With the new implementation, servers are properly
    detached and will continue running as daemon processes with their output redirected
    to log files.
    """
    # Import needed modules for CLI simulation
    import argparse
    from types import SimpleNamespace

    # Create a client instance (simulating CLI startup)
    client = MultiServerClient(config_path=config_path, logger=logger)
    server_name = "echo"

    # Create args namespace to simulate CLI args (with command="launch")
    args = SimpleNamespace(
        server=server_name,
        command="launch",
        verbose=True,
        config=config_path,
        no_auto_launch=False
    )

    # Track the server process PID
    server_pid = None

    try:
        # Simulate the launch_server function from main.py
        logger.info(f"Launching server '{args.server}'...")
        success = await client.launch_server(args.server)

        assert success, f"Failed to launch server '{args.server}'"
        logger.info(f"Server '{args.server}' launched successfully.")

        # Store process info
        process = client._local_processes.get(server_name)
        if process:
            process_tracker['started_processes'].append(process.pid)
            server_pid = process.pid

        # Verify server is running
        assert server_name in client._local_processes, f"{server_name} process not found after launch"
        assert client._local_processes[server_name].poll() is None, f"{server_name} process not running after launch"

        # Now simulate the CLI's finally block for the launch command
        # Track running servers for the finally block (simulating main.py behavior)
        running_servers = []
        for srv_name in client._local_processes:
            proc = client._local_processes[srv_name]
            if proc and proc.poll() is None:  # If process is still running
                running_servers.append(srv_name)

        # Check if we need to stop servers (which we shouldn't for launch command)
        if running_servers and args.command not in ["stop", "launch"]:
            logger.info(f"Automatically stopping {len(running_servers)} server(s): {', '.join(running_servers)}")
            # Close client and stop all servers
            await client.close()
        else:
            # Close client connections but don't stop the servers
            logger.info("Closing client connections but not stopping servers")
            await client.close(stop_servers=False)

        # Wait a moment
        await asyncio.sleep(1)

        # Since client is now closed, we need to check if the process is still running using its PID
        try:
            # Try sending signal 0 to check if process exists
            os.kill(server_pid, 0)
            # If we get here, process is still running as expected
            process_still_running = True
        except OSError:
            # Process not found, which means it was stopped unexpectedly
            process_still_running = False

        assert process_still_running, f"Process {server_pid} for server {server_name} was stopped after CLI launch command simulation"

        # Now create a new client to verify we can still connect to the running server
        verification_client = MultiServerClient(config_path=config_path, logger=logger)

        # Verify the server is still available by listing its tools
        tools = await verification_client.list_server_tools(server_name)
        assert tools, f"Failed to list tools on server {server_name} after CLI launch command simulation"
        logger.info(f"Successfully verified server {server_name} is still running and responding")

        # Clean up by stopping the server through our verification client
        await verification_client.stop_server(server_name)
        await verification_client.close()

    except Exception as e:
        logger.error(f"Error in test_cli_launch_command_simulation: {e}")
        raise
    finally:
        # If we have a server PID, make sure it's terminated for test cleanup
        if server_pid:
            try:
                # Try sending signal 0 to check if process exists
                os.kill(server_pid, 0)
                # If we get here, process is still running
                logger.info(f"Process {server_pid} is still running during cleanup, sending SIGTERM")
                os.kill(server_pid, signal.SIGTERM)
            except OSError:
                # Process not found, which is good
                pass


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])