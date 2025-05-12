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

The client provides a simple command-line interface:

```bash
# List all configured servers
python main.py -c config.json list

# List available tools on a server
python main.py -c config.json tools --server echo

# Send a query to a server
python main.py -c config.json query --server echo --message "Hello world"

# Call a specific tool
python main.py -c config.json query --server echo --tool ping

# Call a tool with specific arguments
python main.py -c config.json query --server filesystem --tool list_directory --args '{"path": "/path/to/dir"}'

# Launch a server
python main.py -c config.json launch --server echo

# Stop a server
python main.py -c config.json stop --server echo
```

### Python API

```python
import asyncio
from mcp_client_multi_server import MultiServerClient

async def main():
    # Create client with default config location
    client = MultiServerClient()
    
    # Or with custom config
    # client = MultiServerClient(config_path="path/to/config.json")
    
    # List available servers
    servers = client.list_servers()
    print(f"Available servers: {servers}")
    
    # Connect to a server (automatically launches if needed)
    await client.connect("echo")
    
    # List available tools on a server
    tools = await client.list_server_tools("echo")
    print(f"Available tools: {tools}")
    
    # Query a server with message parameter
    response = await client.query_server(
        server_name="echo",
        message="Hello, world!",
        tool_name="process_message"
    )
    print(f"Response: {response}")

    # Query a server with custom arguments
    response = await client.query_server(
        server_name="filesystem",
        tool_name="list_directory",
        args={"path": "/path/to/directory"}
    )
    print(f"Directory listing: {response}")
    
    # Launch a server explicitly
    await client.launch_server("another-server")
    
    # Stop a running server
    await client.stop_server("another-server")
    
    # Close all connections and stop all servers
    await client.close()

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
python -m pytest tests/test_npx_servers.py -v

# Stop after first failure
python run_tests.py -x

# Run specific test file
python -m pytest tests/test_servers.py -v
python -m pytest tests/test_npx_servers.py -v
```

> **Note:** The test suite includes dedicated tests for NPX servers in `test_npx_servers.py`. These tests are more resilient and provide better diagnostics for NPX-related issues.

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

### Fetch Server Example

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

## Additional Server Support

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

This configuration matches how Claude Desktop launches the Playwright server. The server is automatically launched when needed.

**Important Limitation**: The Playwright MCP server **always** binds to port 3001 regardless of how it's launched, and this behavior is hardcoded in the server. Our client has special handling for this limitation:

1. If port 3001 is already in use and is a valid Playwright MCP server (e.g., from Claude Desktop), the client will connect to that existing server.
2. If port 3001 is in use but doesn't appear to be a valid MCP server, the client will warn you that port 3001 must be available to use the Playwright server.

To use the Playwright server:
- Ensure port 3001 is free before launching
- Or use Claude Desktop's instance if it's already running
- If another application is using port 3001, you must stop it before using the Playwright server

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

## License

MIT