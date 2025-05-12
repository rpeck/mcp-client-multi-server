#!/usr/bin/env python
"""
Debug script to test playwright server connectivity.
"""

import os
import sys
import shutil
import logging
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_client_multi_server.client import MultiServerClient


# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("debug_playwright")


def check_npx():
    """Check if npx is available."""
    npx_path = "/opt/homebrew/bin/npx"
    if not os.path.exists(npx_path):
        print(f"Specific NPX path not found: {npx_path}")
        # Try finding it in PATH
        npx_path = shutil.which("npx")
        if not npx_path:
            print("NPX not found in PATH")
            return None
    
    print(f"Found NPX at: {npx_path}")
    return npx_path


def check_package(package_name, npx_path):
    """Try to check if a package is available."""
    import subprocess
    try:
        print(f"Checking if {package_name} is globally installed...")
        result = subprocess.run(
            ["npm", "list", "-g", package_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if "empty" in result.stdout or package_name not in result.stdout:
            print(f"Package {package_name} not found in global packages")
        else:
            print(f"Package {package_name} found in global packages")
            
        # Try running it with npx
        print(f"Trying to run {package_name} with npx...")
        version_result = subprocess.run(
            [npx_path, package_name, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print(f"NPX result: {version_result.stdout}")
        if version_result.stderr:
            print(f"NPX stderr: {version_result.stderr}")
            
    except Exception as e:
        print(f"Error checking package: {e}")


async def test_playwright_connection():
    """Test connecting to the playwright server."""
    # Load config from examples directory
    config_path = str(Path(__file__).parent.parent / "examples" / "config.json")
    print(f"Using config from: {config_path}")
    
    # Create client
    client = MultiServerClient(config_path=config_path, logger=logger)
    
    try:
        # Check if playwright is in server list
        servers = client.list_servers()
        if "playwright" in servers:
            print("Playwright server found in configuration")
        else:
            print("Playwright server not found in configuration")
            print(f"Available servers: {servers}")
            return
            
        # Get server config
        pw_config = client.get_server_config("playwright")
        print(f"Playwright config: {pw_config}")
        
        # Try to connect
        print("Attempting to connect to playwright server...")
        pw_client = await client.connect("playwright")
        
        if pw_client:
            print("Successfully connected to playwright server")
            
            # Try listing tools
            print("Listing tools...")
            async with pw_client:
                tools = await pw_client.list_tools()
                
            if tools:
                print(f"Tools found: {len(tools)}")
                for tool in tools:
                    print(f"- {tool.name}: {getattr(tool, 'description', 'No description')}")
            else:
                print("No tools found")
                
        else:
            print("Failed to connect to playwright server")
            
    except Exception as e:
        print(f"Error in test: {e}")
        import traceback
        print(traceback.format_exc())
        
    finally:
        # Clean up
        await client.close()


async def main():
    """Main debug function."""
    # Check NPX availability
    npx_path = check_npx()
    if not npx_path:
        print("Cannot proceed without NPX")
        return
        
    # Check package availability
    check_package("@executeautomation/playwright-mcp-server", npx_path)
    
    # Test connection
    await test_playwright_connection()


if __name__ == "__main__":
    asyncio.run(main())