"""
Tests for error handling and resource cleanup when errors occur.

These tests verify that when errors happen during server operations,
resources are still properly cleaned up, preventing orphaned processes.
"""

import os
import time
import pytest
import logging
import asyncio
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


@pytest.mark.asyncio
async def test_cleanup_after_error(client, process_tracker):
    """Test that resources are properly cleaned up after an error occurs."""
    # Launch the echo server
    server_name = "echo"
    launch_result = await client.launch_server(server_name)
    assert launch_result, f"Failed to launch {server_name} server"
    
    # Store process info for cleanup verification
    process = client._local_processes.get(server_name)
    if process:
        process_tracker['started_processes'].append(process.pid)
    
    # Verify server is running
    assert server_name in client._local_processes, f"{server_name} process not in _local_processes after launch"
    assert client._local_processes[server_name].poll() is None, f"{server_name} process not running after launch"
    
    try:
        # Simulate an error during test
        response = await client.query_server(
            server_name=server_name,
            tool_name="nonexistent_tool"  # This should trigger an error
        )
        assert False, "Expected an error when calling nonexistent tool"
    except Exception as e:
        logger.info(f"Expected error occurred: {e}")
        # This is expected - ensure process is still tracked for cleanup
        pass
    
    # Now properly close the client and check cleanup
    await client.close()
    
    # Wait a moment to ensure all processes are terminated
    await asyncio.sleep(1)
    
    # Verify server process is gone after cleanup
    assert server_name not in client._local_processes, f"{server_name} process still in _local_processes after close"
    
    # Check if the process is still running
    if process:
        poll_result = process.poll()
        assert poll_result is not None, f"Process for {server_name} is still running after close"


@pytest.mark.asyncio
async def test_error_during_server_launch(client, process_tracker):
    """Test handling of errors during server launch."""
    # Try to launch a nonexistent server - test is successful if this fails cleanly
    server_name = "nonexistent-server"
    
    try:
        # This should return False, not raise an exception
        result = await client.launch_server(server_name)
        assert result is False, "Expected launch_server to return False for nonexistent server"
    except Exception as e:
        assert False, f"launch_server should handle nonexistent servers gracefully but raised: {e}"
    
    # Now launch a real server and verify cleanup still works
    working_server = "echo"
    launch_result = await client.launch_server(working_server)
    assert launch_result, f"Failed to launch {working_server} server"
    
    # Store process info for cleanup verification
    process = client._local_processes.get(working_server)
    if process:
        process_tracker['started_processes'].append(process.pid)
    
    # Close the client and check cleanup
    await client.close()
    
    # Wait a moment to ensure all processes are terminated
    await asyncio.sleep(1)
    
    # Verify server process is gone after cleanup
    assert working_server not in client._local_processes, f"{working_server} process still in _local_processes after close"
    
    # Check if tracked processes are still running
    for pid in process_tracker['started_processes']:
        try:
            # Try sending signal 0 to check if process exists
            os.kill(pid, 0)
            # If we get here, process is still running
            assert False, f"Process {pid} for server is still running after close"
        except OSError:
            # Process not found, which is good
            pass


@pytest.mark.asyncio
async def test_query_with_stopped_server(client, process_tracker):
    """Test querying a server after it has been manually stopped."""
    server_name = "echo"
    
    # First launch and verify
    launch_result = await client.launch_server(server_name)
    assert launch_result, f"Failed to launch {server_name} server"
    
    # Store process info
    process = client._local_processes.get(server_name)
    if process:
        process_tracker['started_processes'].append(process.pid)
    
    # Stop the process manually
    await client.stop_server(server_name)
    
    # Wait a moment to ensure process is terminated
    await asyncio.sleep(0.5)
    
    # Now try to query the stopped server - this should handle the error gracefully
    try:
        response = await client.query_server(
            server_name=server_name,
            tool_name="ping"
        )
        
        # If we get a response, that means auto-launch worked
        assert response is not None, "Expected response from auto-launched server"
        
        # Update the started processes list with newly launched process
        if server_name in client._local_processes:
            new_process = client._local_processes.get(server_name)
            if new_process and new_process.pid:
                process_tracker['started_processes'].append(new_process.pid)
    except Exception as e:
        # If auto_launch is True, we should eventually get a response
        if client._auto_launch:
            assert False, f"Query should re-launch stopped server with auto_launch=True, but got error: {e}"
    
    # Clean up
    await client.close()
    
    # Check if tracked processes are still running
    for pid in process_tracker['started_processes']:
        try:
            # Try sending signal 0 to check if process exists
            os.kill(pid, 0)
            # If we get here, process is still running
            assert False, f"Process {pid} for server is still running after close"
        except OSError:
            # Process not found, which is good
            pass


@pytest.mark.asyncio
async def test_cleanup_after_abnormal_termination(config_path, process_tracker):
    """Test that resources are cleaned up even if server terminates abnormally."""
    # Create client
    client = MultiServerClient(config_path=config_path, logger=logger)
    
    # Launch the echo server
    server_name = "echo"
    launch_result = await client.launch_server(server_name)
    assert launch_result, f"Failed to launch {server_name} server"
    
    # Store process info for cleanup verification
    process = client._local_processes.get(server_name)
    assert process is not None, "Process should exist after launch"
    process_tracker['started_processes'].append(process.pid)
    
    # Verify server is running
    assert server_name in client._local_processes, f"{server_name} process not in _local_processes after launch"
    assert client._local_processes[server_name].poll() is None, f"{server_name} process not running after launch"
    
    # Simulate the process exiting abnormally
    try:
        # Terminate the process directly
        process.terminate()
        
        # Wait a moment for process to terminate
        await asyncio.sleep(0.5)
        
        # Verify process has stopped
        assert process.poll() is not None, "Process should have terminated"
        
        # Now try to query the server - client should detect the process is gone
        result = await client.query_server(
            server_name=server_name,
            tool_name="ping"
        )
        
        # If auto_launch is enabled, client will relaunch the process
        if client._auto_launch:
            # The server should exist in the client's local processes
            assert server_name in client._local_processes, "Server should have been auto-launched"
            new_process = client._local_processes.get(server_name)
            assert new_process is not None, "New process should exist after auto-launch"

            # Note: In some implementations, the client may reuse the existing process object
            # but the actual OS process is a new one, so we can't reliably check PID differences

            # Add the new process to tracking if it's not already there
            if new_process.pid not in process_tracker['started_processes']:
                process_tracker['started_processes'].append(new_process.pid)
        else:
            # Without auto-launch, we should get an error
            assert result is None, "Expected None result when querying terminated server without auto-launch"
    finally:
        # Clean up
        await client.close()
        
        # Wait a moment to ensure all processes are terminated
        await asyncio.sleep(1)
        
        # Check if tracked processes are still running
        for pid in process_tracker['started_processes']:
            try:
                # Try sending signal 0 to check if process exists
                os.kill(pid, 0)
                # If we get here, process is still running
                assert False, f"Process {pid} for server is still running after close"
            except OSError:
                # Process not found, which is good
                pass


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])