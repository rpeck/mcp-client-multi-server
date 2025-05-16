#!/usr/bin/env python3
"""
Test script to verify the fixed crunchbase server with progress method fix.
This script focuses on testing the progress method, not the authentication.
"""

import os
import sys
import json
import logging
import asyncio
import socket
from mcp_client_multi_server import MultiServerClient
from fastmcp.client.transports import StreamableHttpTransport

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_fixed_crunchbase")

def check_port_in_use(port, host='127.0.0.1'):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

async def test_crunchbase():
    """Test the fixed crunchbase server using the standard configuration."""
    # Load config from examples/config.json
    config_path = os.path.join(os.path.dirname(__file__), "examples/config.json")
    client = MultiServerClient(config_path=config_path)
    
    port_in_use = check_port_in_use(8000)
    do_shutdown = False
    
    try:
        # Only try to start the server if port 8000 is not in use
        if not port_in_use:
            logger.info("Starting crunchbase server...")
            success = await client.launch_server("crunchbase")
            if not success:
                logger.warning("Failed to launch crunchbase server, but will try to connect anyway")
            else:
                logger.info("Crunchbase server launched successfully")
                do_shutdown = True
                
            # Wait a moment for the server to fully initialize
            await asyncio.sleep(2)
        else:
            logger.info("Port 8000 is already in use, assuming crunchbase server is running")
            
        # Connect to the HTTP transport version (streamable-http on port 8000)
        logger.info("Connecting to crunchbase server via HTTP transport...")
        await client.connect("crunchbase-http")
        
        # Check the available tools
        logger.info("Listing tools from crunchbase server...")
        tools = await client.list_server_tools("crunchbase-http")
        if tools:
            logger.info(f"Available tools: {[tool['name'] for tool in tools]}")
        else:
            logger.error("Failed to list tools. Server might not be running correctly.")
            return False
            
        # ======= PROGRESS METHOD TEST =======
        # Create a special client that lets us capture progress events
        test_result = {
            "progress_events": [],
            "success": False
        }
        
        class ProgressMonitoringClient(MultiServerClient):
            """Special client that monitors progress events."""
            
            async def test_progress_monitoring(self):
                """Run a test that monitors progress events."""
                # Create a special transport that captures progress events
                url = "http://localhost:8000/mcp/stream"
                transport = ProgressMonitoringTransport(url)
                
                # Set the reference to our test result
                transport.test_result = test_result
                
                # Create a client with this transport
                from fastmcp import Client
                client = Client(transport)
                
                try:
                    # Store the client so it doesn't get garbage collected
                    self._special_client = client
                    
                    async with client:
                        # Call a tool that should use progress reporting
                        logger.info("Testing progress reporting with search query...")
                        result = await client.call_tool("search_company_name", {"query": "Google"})
                        
                        # Check if we captured any progress events
                        if test_result["progress_events"]:
                            logger.info(f"Captured {len(test_result['progress_events'])} progress events!")
                            for i, event in enumerate(test_result["progress_events"]):
                                logger.info(f"Progress event {i+1}: {event}")
                            test_result["success"] = True
                            return True
                        else:
                            logger.error("No progress events captured. The progress method fix might not be working.")
                            return False
                        
                except Exception as e:
                    logger.error(f"Error in progress test: {e}")
                    return False
        
        class ProgressMonitoringTransport(StreamableHttpTransport):
            """Transport that tracks progress events."""
            
            def __init__(self, url, **kwargs):
                super().__init__(url, **kwargs)
                self.test_result = None
                
            async def _handle_event(self, event):
                """Capture progress events while handling normally."""
                # Extract the event type and check if it's a progress event
                if hasattr(event, "event_type") and event.event_type == "progress":
                    if self.test_result is not None:
                        # Record progress event
                        event_data = {
                            "position": getattr(event, "position", None),
                            "total": getattr(event, "total", None)
                        }
                        self.test_result["progress_events"].append(event_data)
                        logger.info(f"Captured progress event: {event_data}")
                
                # Handle normally
                return await super()._handle_event(event)
        
        # Create our special client for testing progress events
        progress_client = ProgressMonitoringClient(config_path=config_path)
        progress_result = await progress_client.test_progress_monitoring()
        
        # Close the special client
        await progress_client.close()
        
        # If authentication fails, we'll still consider the test successful
        # if we detected progress events, since we're testing the progress method fix
        # not the authentication
        if test_result["success"]:
            logger.info("Progress method test completed successfully!")
            logger.info(f"Detected {len(test_result['progress_events'])} progress events")
            return True
        else:
            logger.error("Progress method test failed - no progress events detected")
            return False
            
    except Exception as e:
        logger.error(f"Error testing crunchbase server: {e}")
        return False
    finally:
        # Close the client
        await client.close(stop_servers=do_shutdown)

if __name__ == "__main__":
    result = asyncio.run(test_crunchbase())
    if result:
        logger.info("Crunchbase server test completed successfully!")
        sys.exit(0)
    else:
        logger.error("Crunchbase server test failed!")
        sys.exit(1)