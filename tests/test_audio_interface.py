"""
Tests for the audio interface server.

These tests verify that the audio interface server can be launched
and that error messages are properly displayed when dependencies are missing.
"""

import os
import pytest
import asyncio
import subprocess
from pathlib import Path

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


class TestAudioInterface:
    """Tests for the audio interface server."""
    
    async def test_audio_interface_config(self, client):
        """Test that the audio-interface server has the correct configuration."""
        # Check if the server is configured
        assert "audio-interface" in client._config["mcpServers"], "audio-interface not in configuration"
        
        # Check if the configuration has required fields
        server_config = client._config["mcpServers"]["audio-interface"]
        assert "type" in server_config, "Missing 'type' in configuration"
        assert server_config["type"] == "stdio", "Incorrect 'type' value"
        assert "command" in server_config, "Missing 'command' in configuration"
        assert "args" in server_config, "Missing 'args' in configuration"
        assert "env" in server_config, "Missing 'env' in configuration"
        
        # Check if the args point to the audio server script
        assert any("audio_server.py" in arg for arg in server_config["args"]), "audio_server.py not in args"
    
    @pytest.mark.xfail(reason="May fail if audio dependencies are not installed")
    async def test_audio_interface_launch(self, client):
        """Test launching the audio-interface server."""
        try:
            # Attempt to launch the server
            success = await client.launch_server("audio-interface")
            
            # The test may pass or fail depending on whether the dependencies are installed
            if success:
                # If successful, verify it's running
                is_running, _ = client._is_server_running("audio-interface")
                assert is_running, "Server should be running after successful launch"
            else:
                # If failed, check if we can access the logs
                log_info = client.get_server_logs("audio-interface")
                assert log_info["stderr"] is not None, "Expected stderr log to be created"
                
                # Print the error for debugging
                print(f"Server launch failed as expected. Error logs are at: {log_info['stderr']}")
                
                # This will be marked as an expected failure
                pytest.xfail("Server launch failed due to missing dependencies")
        finally:
            # Try to stop the server if it's running
            try:
                await client.stop_server("audio-interface")
            except Exception:
                pass
    
    async def test_get_server_logs(self, client):
        """Test that we can get log paths for the audio-interface server."""
        # Launch the server (this may succeed or fail depending on dependencies)
        try:
            await client.launch_server("audio-interface")
        except Exception:
            pass
        
        # Get logs
        log_info = client.get_server_logs("audio-interface")
        
        # Even if the server fails to start, we should have stderr logs
        assert "stderr" in log_info, "stderr key not in log_info"
        
        # Clean up
        try:
            await client.stop_server("audio-interface")
        except Exception:
            pass