#!/usr/bin/env python3
"""
Simple script to test Playwright server port handling.
Checks port 3001 availability and provides guidance on resolving conflicts.
"""

import asyncio
import logging
import socket
import sys
import subprocess
from pathlib import Path
from mcp_client_multi_server.client import MultiServerClient

def check_port_availability(port=3001):
    """
    Check if port 3001 is available and provide information about what might be using it.

    Returns:
        tuple: (is_available, message, process_info)
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', port))
    sock.close()

    if result == 0:  # Port is in use
        # Try to get information about what's using the port
        process_info = None
        try:
            if sys.platform == 'darwin' or sys.platform.startswith('linux'):  # macOS or Linux
                # Use lsof to get process info
                lsof_output = subprocess.check_output(
                    ['lsof', '-i', f':{port}'],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                process_info = lsof_output
            elif sys.platform == 'win32':  # Windows
                # Use netstat to get process info
                netstat_output = subprocess.check_output(
                    ['netstat', '-ano', '|', 'findstr', f':{port}'],
                    stderr=subprocess.STDOUT,
                    shell=True,
                    universal_newlines=True
                )
                process_info = netstat_output
        except (subprocess.SubprocessError, FileNotFoundError):
            process_info = "Could not determine which process is using the port."

        message = (
            f"Port {port} is already in use. The Playwright MCP server requires this specific port. "
            f"Please terminate the process using port {port} before running this test."
        )
        return False, message, process_info
    else:
        return True, f"Port {port} is available", None

async def main():
    # Set up logging
    logger = logging.getLogger("playwright_test")
    logger.setLevel(logging.DEBUG)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # First check if port 3001 is available
    is_available, message, process_info = check_port_availability()

    if not is_available:
        logger.error(message)
        if process_info:
            logger.error(f"Process information:\n{process_info}")
        logger.error("To fix this issue, you can:")
        logger.error("1. Terminate the process using port 3001")
        logger.error("2. On macOS/Linux: kill <PID> (where PID is the process ID)")
        logger.error("3. On Windows: taskkill /F /PID <PID>")
        logger.error("4. Alternatively, stop any web servers or development servers that might be using this port")
        return

    # Path to config file
    config_path = Path(__file__).parent / "examples" / "config.json"

    # Create client
    client = MultiServerClient(config_path=str(config_path), logger=logger)

    try:
        # Try to connect to the Playwright server
        logger.info("Port 3001 is available. Attempting to connect to Playwright server...")
        playwright_client = await client.connect("playwright")

        if playwright_client:
            logger.info("Successfully connected to Playwright server")

            # Check if we can list tools
            async with playwright_client:
                try:
                    tools = await playwright_client.list_tools()
                    tool_names = [tool.name for tool in tools]
                    logger.info(f"Found {len(tools)} tools: {tool_names}")
                except Exception as e:
                    logger.error(f"Error listing tools: {e}")
        else:
            logger.error("Failed to connect to Playwright server")
            logger.error("This may be because the Playwright MCP server package is not installed.")
            logger.error("Try running: npm install -g @executeautomation/playwright-mcp-server")
    except Exception as e:
        logger.error(f"Error connecting to Playwright server: {e}")
    finally:
        # Clean up
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())