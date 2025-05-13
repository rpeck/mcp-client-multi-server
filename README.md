# MCP Multi-Server Client

A Python client for connecting to multiple Model Context Protocol (MCP) servers simultaneously. This client is compatible with Claude Desktop's configuration format and supports various server types including Python scripts, Node.js applications, and npx packages.

## Features

- **Multi-server support**: Connect to and manage multiple MCP servers from a single client
- **Claude Desktop compatibility**: Uses the same configuration format as Claude Desktop
- **Server launching**: Automatically launch local servers when needed
- **Transport flexibility**: Support for WebSockets, SSE, stdio, and other transport types
- **Simple query interface**: Easy-to-use API for sending messages to specific servers
- **Tool discovery**: List available tools from each server
- **NPX server support**: Custom transport handling for npm-based MCP servers

## Installation

```bash
# Install from PyPI (once published)
pip install mcp-client-multi-server

# Or install from source
git clone https://github.com/yourusername/mcp-client-multi-server.git
cd mcp-client-multi-server
pip install -e .
```

## Configuration

By default, the client looks for a configuration file at:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

You can also specify a custom configuration file when creating the client.

### Sample Configuration

```json
{
  "mcpServers": {
    "python-server": {
      "type": "stdio",
      "command": "python",
      "args": ["path/to/server.py"],
      "env": {
        "API_KEY": "your-api-key-here"
      }
    },
    "node-server": {
      "type": "stdio",
      "command": "node",
      "args": ["path/to/server.js"],
      "env": {
        "NODE_ENV": "production"
      }
    },
    "npx-server": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allow"],
      "env": {
        "DEBUG": "true"
      }
    },
    "remote-server": {
      "url": "wss://example.com/mcp"
    }
  }
}
```

## Usage

### Command Line Interface

The client provides a simple command-line interface with commands for managing servers, listing tools, and executing queries.

#### General Commands

```bash
# List all configured servers
python main.py -c config.json list

# List available tools on any server
python main.py -c config.json tools --server <server-name>

# Launch any server explicitly
python main.py -c config.json launch --server <server-name>

# Stop any running server
python main.py -c config.json stop --server <server-name>

# Show help and available commands
python main.py --help
```

#### Server-Specific Examples

Here are examples for different server types:

##### Echo Server

```bash
# List echo server tools
python main.py -c config.json tools --server echo

# Send a simple message to the echo server
python main.py -c config.json query --server echo --message "Hello world"

# Use the ping tool explicitly
python main.py -c config.json query --server echo --tool ping
```

##### Filesystem Server

```bash
# List filesystem server tools
python main.py -c config.json tools --server filesystem

# List files in a directory (use --message parameter for JSON arguments)
python main.py -c config.json query --server filesystem --tool list_directory --message '{"path": "/path/to/dir"}'

# Read a file
python main.py -c config.json query --server filesystem --tool read_file --message '{"path": "/path/to/file.txt"}'

# Write to a file
python main.py -c config.json query --server filesystem --tool write_file --message '{"path": "/path/to/file.txt", "content": "Hello, world!"}'
```

##### Fetch Server

```bash
# List fetch server tools
python main.py -c config.json tools --server fetch

# Fetch a web page (using message parameter)
python main.py -c config.json query --server fetch --message "https://example.com"

# Fetch a web page (using tool and args)
python main.py -c config.json query --server fetch --tool fetch --message '{"url": "https://example.com"}'

# Fetch with additional parameters
python main.py -c config.json query --server fetch --tool fetch --message '{
  "url": "https://example.com",
  "method": "GET",
  "headers": {"User-Agent": "MCP Client"}
}'
```

##### Sequential Thinking Server

```bash
# List sequential-thinking server tools
python main.py -c config.json tools --server sequential-thinking

# View server information
python main.py -c config.json query --server sequential-thinking --tool server_info

# Start a thinking sequence with first thought
# Note: This will require LLM sampling support to complete properly
python main.py -c config.json query --server sequential-thinking --tool sequentialthinking --message '{
  "thought": "First, I need to understand the problem...",
  "thoughtNumber": 1,
  "totalThoughts": 5,
  "nextThoughtNeeded": true
}'
```

##### Playwright Server

```bash
# List playwright server tools
python main.py -c config.json tools --server playwright

# Navigate to a website
python main.py -c config.json query --server playwright --tool playwright_navigate --message '{"url": "https://example.com"}'

# Take a screenshot
python main.py -c config.json query --server playwright --tool playwright_screenshot

# Click an element
python main.py -c config.json query --server playwright --tool playwright_click --message '{"selector": "a.example-link"}'
```

## Using as a Module

The MCP Multi-Server Client is designed to be easily integrated into other Python applications. This section covers key usage patterns for developers who want to use the client as a module.

### Basic Usage

```python
import asyncio
from mcp_client_multi_server import MultiServerClient

async def main():
    # Create client with default config (looks in standard Claude Desktop locations)
    client = MultiServerClient()

    # Or with custom config path
    # client = MultiServerClient(config_path="path/to/config.json")

    # Or with direct configuration dictionary
    # custom_config = {"mcpServers": {"my-server": {"type": "stdio", "command": "python", "args": ["server.py"]}}}
    # client = MultiServerClient(custom_config=custom_config)

    try:
        # Get a list of configured servers
        servers = client.list_servers()
        print(f"Available servers: {servers}")

        # Connect to a server (will auto-launch if needed and auto_launch=True)
        await client.connect("echo")

        # Query a server with a message
        response = await client.query_server(
            server_name="echo",
            message="Hello, world!"
        )
        print(f"Response: {response}")

    finally:
        # Close client, stopping STDIO servers
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Advanced Usage with Custom Lifecycle Management

```python
import asyncio
import logging
from mcp_client_multi_server import MultiServerClient

# Set up logging if needed
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_application")

async def run_mcp_operations():
    # Create client with logging and disable auto-launch
    client = MultiServerClient(
        config_path="config.json",
        logger=logger,
        auto_launch=False  # Don't auto-launch servers when connecting
    )

    try:
        # Check if servers are running
        servers = client.list_servers()
        for server in servers:
            is_running, pid = client._is_server_running(server)
            if is_running:
                print(f"Server {server} is already running (PID: {pid})")
            else:
                print(f"Server {server} is not running")

        # Launch servers explicitly and let them persist
        echo_server = "echo"
        await client.launch_server(echo_server)
        print(f"Launched {echo_server} server")

        # List available tools
        tools = await client.list_server_tools(echo_server)
        print(f"Available tools on {echo_server}: {[tool['name'] for tool in tools]}")

        # Execute multiple operations
        for i in range(3):
            response = await client.query_server(
                server_name=echo_server,
                message=f"Message {i}",
                tool_name="process_message"
            )
            print(f"Response {i}: {response}")

        # Query with custom arguments
        custom_args = {"param1": "value1", "param2": "value2"}
        response = await client.query_server(
            server_name=echo_server,
            tool_name="ping",
            args=custom_args
        )
        print(f"Custom args response: {response}")

    finally:
        # Close client connections but don't stop servers
        # Servers will continue running for future use
        await client.close(stop_servers=False)

if __name__ == "__main__":
    asyncio.run(run_mcp_operations())
```

### Working with Multiple Servers

```python
import asyncio
from mcp_client_multi_server import MultiServerClient

async def work_with_multiple_servers():
    client = MultiServerClient(config_path="config.json")

    try:
        # Launch servers that should persist across client instances
        await client.launch_server("filesystem")

        # For specialized operations, work directly with multiple servers
        filesystem_tools = await client.list_server_tools("filesystem")
        echo_tools = await client.list_server_tools("echo")

        # Combine operations from multiple servers
        file_list = await client.query_server(
            server_name="filesystem",
            tool_name="list_directory",
            args={"path": "/path/to/dir"}
        )

        for file in file_list:
            # Read a file with filesystem server
            file_content = await client.query_server(
                server_name="filesystem",
                tool_name="read_file",
                args={"path": file}
            )

            # Process the content with echo server
            processed = await client.query_server(
                server_name="echo",
                message=file_content
            )

            # Do something with the processed content
            print(f"Processed {file}: {processed}")

    finally:
        # Close the client, but don't stop servers that were explicitly launched
        # This will only stop servers that were auto-launched during query operations
        await client.close()

if __name__ == "__main__":
    asyncio.run(work_with_multiple_servers())
```

### Integration with Web Applications

```python
from fastapi import FastAPI, BackgroundTasks
from mcp_client_multi_server import MultiServerClient
import uvicorn
import asyncio

app = FastAPI()

# Global client shared across requests
client = None

@app.on_event("startup")
async def startup_event():
    """Initialize the MCP client when the app starts."""
    global client
    client = MultiServerClient(config_path="config.json")

    # Launch any critical servers at startup
    await client.launch_server("echo")
    await client.launch_server("filesystem")
    print("MCP servers initialized and ready")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up the MCP client when the app shuts down."""
    global client
    if client:
        # Close connections but don't stop servers
        # Let them keep running for subsequent app restarts
        await client.close(stop_servers=False)
        print("MCP client connections closed")

@app.get("/query/{server}")
async def query_server(server: str, message: str):
    """Query an MCP server with a message."""
    response = await client.query_server(
        server_name=server,
        message=message
    )
    return {"result": response}

@app.post("/launch/{server}")
async def launch_server(server: str, background_tasks: BackgroundTasks):
    """Launch an MCP server in the background."""
    background_tasks.add_task(client.launch_server, server)
    return {"status": f"Server {server} launch initiated"}

@app.get("/status")
async def get_status():
    """Get status of all configured servers."""
    servers = client.list_servers()
    result = {}

    for server in servers:
        is_running, pid = client._is_server_running(server)
        result[server] = {
            "running": is_running,
            "pid": pid if is_running else None
        }

    return result

@app.post("/stop/{server}")
async def stop_server(server: str):
    """Stop a specific MCP server."""
    success = await client.stop_server(server)
    return {"status": "stopped" if success else "failed"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Error Handling and Reconnection

```python
import asyncio
import time
from mcp_client_multi_server import MultiServerClient

class MCPApplicationClient:
    """Application-specific wrapper for MultiServerClient with error handling."""

    def __init__(self, config_path=None):
        self.config_path = config_path
        self.client = None
        self.initialized = False

    async def initialize(self):
        """Initialize the MCP client with error handling."""
        if self.client is None:
            try:
                self.client = MultiServerClient(config_path=self.config_path)
                self.initialized = True
            except Exception as e:
                print(f"Error initializing MCP client: {e}")
                raise
        return self.client

    async def query_with_retry(self, server_name, message=None, tool_name="process_message",
                              args=None, max_retries=3, retry_delay=1.0):
        """Query a server with automatic retries and reconnection."""
        if not self.initialized:
            await self.initialize()

        retries = 0
        while retries < max_retries:
            try:
                response = await self.client.query_server(
                    server_name=server_name,
                    message=message,
                    tool_name=tool_name,
                    args=args
                )
                return response
            except Exception as e:
                retries += 1
                print(f"Error querying server {server_name} (attempt {retries}/{max_retries}): {e}")

                if retries >= max_retries:
                    raise

                # Check if server is running, restart if needed
                is_running, _ = self.client._is_server_running(server_name)
                if not is_running:
                    print(f"Server {server_name} not running, attempting to relaunch...")
                    await self.client.launch_server(server_name)

                # Wait before retrying
                await asyncio.sleep(retry_delay)

        # This should not be reached due to the raise in the loop
        raise Exception(f"Failed to query server {server_name} after {max_retries} attempts")

    async def close(self, stop_servers=False):
        """Close the client safely."""
        if self.client:
            await self.client.close(stop_servers=stop_servers)
            self.client = None
            self.initialized = False

# Example usage
async def main():
    app_client = MCPApplicationClient(config_path="config.json")

    try:
        # Initialize client
        await app_client.initialize()

        # Use with retry capability
        response = await app_client.query_with_retry(
            server_name="echo",
            message="Hello with automatic retry"
        )
        print(f"Response: {response}")

    finally:
        # Clean up
        await app_client.close(stop_servers=True)

if __name__ == "__main__":
    asyncio.run(main())
```

## Running Tests

The project includes comprehensive tests for both Python and npx-based MCP servers.

### Prerequisites

#### Python Dependencies

Install Python test dependencies:

```bash
# Using pip
python -m pip install pytest pytest-asyncio

# Using uv
uv pip install pytest pytest-asyncio

# Or install development dependencies
pip install -e ".[dev]"
```

#### NPM Dependencies

The npx server tests require specific npm packages:

```bash
# Install filesystem server package globally
npm install -g @modelcontextprotocol/server-filesystem
```

Note:
- The npx-related tests will be skipped automatically if these packages are not installed.
- Even with the package installed, you might still see some tests skipped due to permissions or other environmental factors.
- The tests are designed to handle these cases gracefully by skipping rather than failing.
- If you see "Skipping npx server test, possible missing package", check that you have the npm package installed and the test config properly references its location.

### Test Commands

```bash
# Run all tests
python run_tests.py

# Run tests with verbose output
python run_tests.py -v

# Run only Python server tests
python run_tests.py --python-only

# Run only npx server tests
python run_tests.py --npx-only

# Run only server cleanup and error handling tests
python run_tests.py --cleanup-only

# Run all tests including slower ones
python run_tests.py --all

# Skip slower tests (good for CI environments)
python run_tests.py --skip-slow

# Stop after first failure
python run_tests.py -x

# Run specific test file
python -m pytest tests/test_servers.py -v
python -m pytest tests/test_npx_servers.py -v
python -m pytest tests/test_server_cleanup.py -v

# Run API documentation tests
python -m pytest tests/test_module_integration_examples.py -v
```

> **Note:** The test suite includes dedicated tests for NPX servers in `test_npx_servers.py`. These tests are more resilient and provide better diagnostics for NPX-related issues.

### API Documentation Tests

The `test_module_integration_examples.py` test file serves as both validation and executable documentation for the API examples in the README. These tests ensure that the documented patterns work as expected:

```bash
# Run all API documentation tests
python -m pytest tests/test_module_integration_examples.py -v

# Run a specific API example test
python -m pytest tests/test_module_integration_examples.py::TestBasicUsageExample -v
python -m pytest tests/test_module_integration_examples.py::TestAdvancedUsageExample -v
python -m pytest tests/test_module_integration_examples.py::TestMultipleServersExample -v
python -m pytest tests/test_module_integration_examples.py::TestWebApplicationExample -v
python -m pytest tests/test_module_integration_examples.py::TestErrorHandlingExample -v
```

If you update the API examples in the README, you should also update the corresponding test cases to ensure they remain in sync. This provides:

1. Verification that the documented examples work correctly
2. Early detection if API changes break the documented patterns
3. Executable examples that demonstrate correct API usage

The tests verify:
- Configuration loading
- Connection to Python and npx servers
- Tool discovery
- Message processing
- Server launching and stopping
- Response validation
- Tool parameter passing
- Directory listing verification
- Exact response content validation
- Proper use of the custom NpxProcessTransport
- Server resource cleanup
- Error handling and recovery
- Process tracking and orphan prevention
- Server functionality validation

### Writing Custom Tests

The test suite provides patterns for testing MCP servers and clients that you can adapt for your own testing:

```python
import pytest
from mcp_client_multi_server import MultiServerClient

@pytest.mark.asyncio
async def test_custom_tool(client):
    """Test a custom tool on your MCP server."""
    # Call a tool with specific arguments
    response = await client.query_server(
        server_name="your-server",
        tool_name="your-custom-tool",
        args={"param1": "value1", "param2": "value2"}
    )

    # Verify response format and content
    assert response is not None, "Failed to get response"

    # For text responses
    if isinstance(response, str) or hasattr(response, "text"):
        response_text = response.text if hasattr(response, "text") else str(response)
        assert "expected content" in response_text

    # For structured responses
    if isinstance(response, list):
        # Test list responses
        assert len(response) > 0, "Empty response received"
        # Test specific fields in first item
        if isinstance(response[0], dict):
            assert "expected_field" in response[0]
    elif isinstance(response, dict):
        # Test dictionary responses
        assert "expected_key" in response
```

## Included Examples

The project comes with example servers and configurations:

- `examples/echo_server.py`: A simple Python-based MCP server that echoes messages
- `examples/config.json`: Sample configuration file with multiple server types

## Supported Server Types

The client supports various MCP server types:

- **Python scripts**: Run directly with Python
- **Node.js scripts**: Run with Node.js
- **NPX packages**: Run from npm registry without installation
- **UVX packages**: Run using the UVX package runner
- **Remote servers**: Connect via WebSockets or SSE
- **Sequential thinking**: MCP server for step-by-step thinking
- **Playwright**: Web automation (requires an HTTP server)

## NPX Server Support

The client includes a custom `NpxProcessTransport` class that properly handles npm-based MCP servers. When configuring an npx-based server:

1. Set `"command": "npx"` - The npx executable path
2. Include `"args": ["-y", "package-name", "additional-args"]` - The package name and any additional arguments
3. Use `"type": "stdio"` - Must be stdio type for local npx servers

## UVX Server Support

The client also supports UVX-based MCP servers. When configuring a uvx-based server:

1. Set `"command": "uvx"` or the full path to the uvx executable
2. Include `"args": ["package-name", "additional-args"]` - The package name and any additional arguments
3. Use `"type": "stdio"` - Must be stdio type for local uvx servers

## Server-Specific Configuration and Features

### Fetch Server

The client provides special handling for the fetch server's URL parameter:

```json
{
  "mcpServers": {
    "fetch": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-fetch"],
      "env": {}
    }
  }
}
```

To use the fetch server from the command line:

```bash
python main.py -c config.json query --server fetch --tool fetch --message "https://example.com"
```

The client automatically converts the message to a URL parameter when using the fetch server.

### Sequential Thinking Server

The client supports the Sequential Thinking MCP server, which enables step-by-step thinking capabilities:

```json
{
  "mcpServers": {
    "sequential-thinking": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sequential-thinking"
      ],
      "env": {}
    }
  }
}
```

**Important Note on Sampling**: The Sequential Thinking server uses MCP sampling callbacks to request LLM completions from the client. These callbacks require an LLM-enabled client (like Claude Desktop) to handle the sampling requests. When using this server programmatically without an LLM-enabled client, some tools may not function correctly. Basic connection and tool listing will work, but tools that require LLM reasoning will need a proper sampling callback implementation.

### Playwright Server

The Playwright server is configured as a stdio-based process, similar to other NPX-based servers:

```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@executeautomation/playwright-mcp-server"]
    }
  }
}
```

**Important Limitation**: The Playwright MCP server **always** binds to port 3001 regardless of how it's launched, and this behavior is hardcoded in the server. Our client has special handling for this limitation:

1. If port 3001 is already in use and is a valid Playwright MCP server (e.g., from Claude Desktop), the client will connect to that existing server.
2. If port 3001 is in use but doesn't appear to be a valid MCP server, the client will warn you that port 3001 must be available to use the Playwright server.

To use the Playwright server:
- Ensure port 3001 is free before launching
- Or use Claude Desktop's instance if it's already running
- If another application is using port 3001, you must stop it before using the Playwright server

This configuration matches how Claude Desktop launches the Playwright server. The server is automatically launched when needed.

### Required NPM Packages

To use npx-based MCP servers, the corresponding npm packages must be installed either globally or locally in your project:

```bash
# Install globally
npm install -g @modelcontextprotocol/server-filesystem

# Or install locally in your project
npm install @modelcontextprotocol/server-filesystem
```

The client will use `npx` to run these packages on demand. The `-y` flag in the configuration automatically answers "yes" to any installation prompts, but having the packages pre-installed ensures faster startup and avoids unexpected network requests.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Server Lifecycle Management

The client includes intelligent server lifecycle management to handle different types of servers appropriately:

### Server Types and Lifecycle

- **Local STDIO Servers**: Servers that rely on stdin/stdout pipes for communication (Python scripts, Node.js scripts, etc.) are automatically stopped when the client exits, unless specifically requested to keep running.

- **Socket-based Servers**: Servers that use Unix or TCP sockets for communication can remain running after the client exits and be reconnected to by future client instances.

- **Remote Servers**: For HTTP/WebSocket servers, the client only disconnects but never attempts to stop them.

### Server Registry

The client maintains a registry of running servers in `~/.mcp-client-multi-server/servers.json`, which includes:

- Server name and PID
- Log file locations
- Start time
- Configuration hash

This allows the client to:
1. Detect running servers across different client instances
2. Track log files for each server
3. Reconnect to existing servers rather than launching new instances
4. Properly clean up resources when servers are stopped

### Using Server Lifecycle Features

#### Launch Command

The `launch` command explicitly starts a server and keeps it running even after the client exits:

```bash
# Launch a server that will persist after client exit
python main.py -c config.json launch --server echo
```

#### Stop and Stop-All Commands

```bash
# Stop a specific server
python main.py -c config.json stop --server echo

# Stop all running servers
python main.py -c config.json stop-all
```

#### Automatic Stopping Behavior

By default, when using other commands like `query` or `tools`, local STDIO servers are automatically stopped when the client exits. This behavior can be controlled programmatically:

```python
# Create client
client = MultiServerClient()

# Close client but keep servers running
await client.close(stop_servers=False)

# Close client and stop local STDIO servers
await client.close(stop_servers=True)
```

## Future Development

### TODOs for Server Lifecycle Management

The current implementation provides robust, transport-specific server lifecycle management, but several enhancements could be made in future updates:

#### Process Persistence Improvements

- **Platform-specific Detachment**: Further enhance platform-specific process detachment techniques, especially for macOS and Windows, to ensure servers persist reliably when intended.

- **Socket Path Detection**: Implement more sophisticated detection of socket-based servers vs pipe-based STDIO servers for more accurate lifecycle management.

- **Transport Auto-Discovery**: Develop smarter transport type detection based on server configuration and runtime behavior.

#### Server Registry Enhancements

- **PID Validation**: Improve the accuracy of detecting existing server processes by considering additional metadata beyond just the PID.

- **Socket Reconnection**: Enhance reconnection to servers that use STDIO over sockets or IPC, allowing true persistence across client sessions.

- **Server Discovery**: Add auto-discovery of running servers based on well-known socket paths or ports.

- **Config Comparison**: Add validation to ensure server configs haven't changed before reusing an existing server.

#### CLI and Monitoring Improvements

- **Server Status**: Provide more detailed status information for each server, including uptime, client connections, and resource usage.

- **Interactive Mode**: Add an interactive shell mode for the CLI for easier server management.

- **Server Logs**: Provide commands to view, filter, and analyze server logs directly from the CLI.

- **Process Monitoring**: Add optional monitoring of server health with automatic recovery for critical servers.

## License

MIT