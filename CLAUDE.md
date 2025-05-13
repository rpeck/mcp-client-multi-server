# MCP Multi-Server Client

## Overview

MCP Multi-Server Client is a client built on top of the FastMCP library that connects to multiple Model Context Protocol (MCP) servers simultaneously. It provides support for the Claude Desktop configuration format, automatic server launching, and a simple query interface.

## Key Features

- **Multi-server support**: Connect to and manage multiple MCP servers from a single client
- **Claude Desktop compatibility**: Uses the same configuration format as Claude Desktop
- **Server launching**: Automatically launch local servers when needed
- **Transport flexibility**: Support for WebSockets, SSE, stdio, and other transport types
- **Simple query interface**: Easy-to-use API for sending messages to specific servers
- **Tool discovery**: List available tools from each server
- **NPX server support**: Custom transport handling for npm-based MCP servers

## Project Structure

```
mcp-client-multi-server/
├── mcp_client_multi_server/
│   ├── __init__.py       # Package exports
│   └── client.py         # Main MultiServerClient implementation
├── examples/
│   ├── config.json       # Example configuration
│   └── echo_server.py    # Example MCP server
├── main.py               # CLI entry point
├── README.md             # User documentation
├── CLAUDE.md             # This file
└── pyproject.toml        # Project configuration
```

## Key Components

### MultiServerClient

The core class that manages multiple MCP servers, with the following functionality:

- Loading configuration from standard Claude Desktop locations
- Creating server connections on demand
- Launching and stopping local server processes
- Intelligent server lifecycle management based on transport type
- Sending queries to specific servers
- Listing available tools on servers
- Proper resource cleanup
- Server registry to track running server instances across client lifecycles

### Command Line Interface

The CLI provides commands for:

- `list`: Viewing all configured servers and their running status
- `query`: Sending a message to a specific server (with optional tool selection)
- `launch`: Explicitly launching a local server (persists beyond client execution)
- `stop`: Stopping a specific running server
- `stop-all`: Stopping all running servers
- `tools`: Listing all available tools on a server

### Configuration Format

Uses the Claude Desktop configuration format:

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
    }
  }
}
```

## Development Commands

To run the client:

```bash
# List servers
python main.py -c examples/config.json list

# List available tools on a server
python main.py -c examples/config.json tools --server echo

# Send a query to a server
python main.py -c examples/config.json query --server echo --message "Hello world"

# Call a specific tool
python main.py -c examples/config.json query --server echo --tool ping

# Call a tool with specific arguments (use --message for JSON args)
python main.py -c examples/config.json query --server filesystem --tool list_directory --message '{"path": "/path/to/dir"}'

# Launch a server (persists after client exits)
python main.py -c examples/config.json launch --server echo

# Stop a specific server
python main.py -c examples/config.json stop --server echo

# Stop all running servers
python main.py -c examples/config.json stop-all
```

## Testing

The project includes a comprehensive test suite with specific tests for both Python and npx-based servers.

```bash
# Run all tests
python run_tests.py

# Run tests with verbose output
python run_tests.py -v

# Run only Python server tests
python run_tests.py --python-only

# Run only npx server tests
python run_tests.py --npx-only

# Run specific test file
python -m pytest tests/test_npx_servers.py -v
```

### Documentation and Test Synchronization

**IMPORTANT**: The API examples in the README.md file have corresponding test cases in `tests/test_module_integration_examples.py`. When updating the README examples or the examples in CLAUDE.md, always make corresponding updates to the tests to ensure they stay in sync.

This test file serves as both validation that the examples work as expected and as a form of executable documentation. Any API changes should be reflected in both places to maintain consistency between documentation and actual functionality.

To run the API documentation tests:

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

When making API changes, update these files in this order:
1. Update the code implementation
2. Update the tests in `tests/test_module_integration_examples.py`
3. Update the examples in README.md
4. Update the examples in CLAUDE.md (if applicable)

The tests include verification for all major usage patterns documented in the README:
- Basic client usage
- Advanced usage with custom lifecycle management
- Working with multiple servers
- Web application integration
- Error handling and reconnection strategies

Note: To run npx server tests, you need to install the required npm packages:

```bash
npm install -g @modelcontextprotocol/server-filesystem
```

## Architecture

The client follows a modular design:

1. **Configuration Management**: Handles loading and validation of server configs
2. **Transport Handling**: Creates appropriate transport objects for different server types (Python, Node.js, npx)
3. **Server Management**:
   - Intelligently manages server lifecycles based on transport type
   - Uses a persistent server registry to track running servers
   - Properly handles stdio-based vs socket-based server persistence
   - Automatically detaches server processes for persistence
4. **Client Management**: Creates and manages FastMCP client instances for each server
5. **Query Execution**: Handles sending messages to servers and processing responses
6. **Tool Discovery**: Lists and provides information about available tools on servers

### NPX Server Handling

The client includes a custom `NpxProcessTransport` class that properly handles npm-based MCP servers with the following features:

- Special handling for npx command execution
- Proper parsing of package names and arguments
- Robust subprocess management
- Compatible with servers like `@modelcontextprotocol/server-filesystem`

The implementation draws inspiration from the cline project (https://github.com/cline/cline), which successfully handles npx-based MCP servers through careful subprocess management techniques. Our approach adapts these concepts to work within the FastMCP framework while maintaining compatibility with Claude Desktop's configuration format.

When configuring an npx-based server, ensure you provide:
1. `"command": "npx"` - The npx executable path
2. `"args": ["-y", "package-name", "additional-args"]` - The package name and any additional arguments
3. `"type": "stdio"` - Must be stdio type for local npx servers

## Server Lifecycle Management

The client includes intelligent server lifecycle management with specialized handling for different server types:

### Server Type Classification

The client identifies different types of servers using the `_is_local_stdio_server` method:

- **Local STDIO Servers**: Servers that rely on standard input/output pipes for direct communication with the parent process
  - Python scripts that don't use socket communication
  - Node.js scripts running in stdio mode
  - NPX/UVX-based packages using stdio transport

- **Socket-based Servers**: Servers that use TCP or Unix sockets for communication
  - Socket-based stdio servers
  - Servers with a URL or port specification in their config

- **Remote Servers**: External servers accessed via HTTP, WebSockets or other network protocols
  - Remote MCP servers
  - HTTP/WebSocket-based MCP servers

### Transport-specific Behavior

The client implements transport-specific behavior through the `stop_local_stdio_servers` method:

- **Local STDIO Servers**: These are automatically stopped when the client exits (default behavior) as they depend on the parent process for communication. This prevents orphaned processes.

- **Socket-based Servers**: These are never automatically stopped by the client, as they can operate independently and be reconnected to by future client instances.

- **Remote Servers**: These are never stopped, only disconnected from.

- **Launch Command**: Servers launched explicitly with the `launch` command are meant to persist after the client exits, and won't be automatically stopped.

### Server Registry

The client maintains a persistent registry of running servers in `~/.mcp-client-multi-server/servers.json`:

- **Server Information**:
  - Server name and PID
  - Log file locations for stdout and stderr
  - Start timestamp
  - Configuration hash for verifying consistent configurations
  - Server log directory location

- **Registry Functions**:
  - `_load_server_registry()`: Loads the registry from disk
  - `_save_server_registry()`: Persists registry to disk
  - `_is_server_running()`: Checks if a server is still running using registry info
  - `_compute_config_hash()`: Creates a hash of the server configuration

### Detached Process Management

The client handles processes differently based on platform:

- **Windows**: Uses `CREATE_NEW_PROCESS_GROUP` flag to detach processes
- **macOS**: Uses a combination of `nohup`, `start_new_session=True`, and `os.setpgrp` for robust detachment
- **Unix/Linux**: Uses `start_new_session=True` and `os.setpgrp` for process detachment

All server output is redirected to log files in the `~/.mcp-client-multi-server/logs/` directory with timestamps.

### API Control

The client API provides fine-grained control over server lifecycle:

```python
# Create client
client = MultiServerClient()

# Launch server (intended to persist after client exits)
await client.launch_server("server-name")

# Close client but keep all servers running
await client.close(stop_servers=False)

# Close client and stop only local STDIO servers
await client.close(stop_servers=True)

# Stop a specific server
await client.stop_server("server-name")

# Stop only local STDIO servers
await client.stop_local_stdio_servers()

# Stop all servers (regardless of type)
await client.stop_all_servers()
```

### CLI Commands

The command-line interface provides convenient commands for server management:

```bash
# Launch a server (remains running after client exits)
python main.py -c config.json launch --server echo

# Stop a specific server
python main.py -c config.json stop --server echo

# Stop all running servers
python main.py -c config.json stop-all

# List servers and their status
python main.py -c config.json list
```

## Using as a Module in Applications

This client is designed to be integrated into larger applications as a module. Here are the key patterns for integration:

### Import and Initialization

```python
from mcp_client_multi_server import MultiServerClient

# Initialize with a specific config file
client = MultiServerClient(config_path="/path/to/config.json")

# Initialize with direct configuration
client = MultiServerClient(custom_config={
    "mcpServers": {
        "my-server": {
            "type": "stdio",
            "command": "python",
            "args": ["path/to/server.py"]
        }
    }
})

# Initialize with custom logger
import logging
logger = logging.getLogger("my_app.mcp")
client = MultiServerClient(
    config_path="/path/to/config.json",
    logger=logger,
    auto_launch=True  # Auto-launch servers when connecting (default)
)
```

### Core Usage Patterns

```python
# Connect to a server - automatically launched if not running and auto_launch=True
await client.connect("server-name")

# Or launch a server explicitly - useful for servers that should persist
await client.launch_server("server-name")

# Send a query with a message
response = await client.query_server(
    server_name="server-name",
    message="Your message here"
)

# Send a query with a specific tool and parameters
response = await client.query_server(
    server_name="server-name",
    tool_name="tool_name",
    args={"param1": "value1", "param2": "value2"}
)

# List available tools on a server
tools = await client.list_server_tools("server-name")

# Check if a server is running
is_running, pid = client._is_server_running("server-name")

# Stop a specific server
success = await client.stop_server("server-name")

# Stop all servers
results = await client.stop_all_servers()

# Close client when done, with control over server stopping
await client.close(stop_servers=True)  # Default: stops local STDIO servers
await client.close(stop_servers=False)  # Keep all servers running
```

### Practical Integration Example

```python
import asyncio
from mcp_client_multi_server import MultiServerClient

class MyApplication:
    def __init__(self, config_path):
        self.config_path = config_path
        self.mcp_client = None

    async def initialize(self):
        # Initialize MCP client
        self.mcp_client = MultiServerClient(config_path=self.config_path)

        # Launch long-running servers
        await self.mcp_client.launch_server("filesystem")

        # Check server tools
        tools = await self.mcp_client.list_server_tools("filesystem")
        self.available_tools = [t["name"] for t in tools]

    async def process_file(self, file_path):
        # Use filesystem server to read file
        content = await self.mcp_client.query_server(
            server_name="filesystem",
            tool_name="read_file",
            args={"path": file_path}
        )

        # Additional processing
        return content

    async def cleanup(self):
        # Close client but leave servers running
        if self.mcp_client:
            await self.mcp_client.close(stop_servers=False)

# Usage
async def main():
    app = MyApplication("config.json")
    await app.initialize()

    try:
        result = await app.process_file("/path/to/file.txt")
        print(result)
    finally:
        await app.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

## Integration Points

- **FastMCP**: Uses FastMCP library for protocol operations
- **Claude Desktop**: Compatible with Claude Desktop configuration format
- **Local Servers**: Can launch and manage local MCP servers
- **External Servers**: Can connect to remote servers via WebSockets or SSE
- **NPX Packages**: Works with MCP servers delivered as npm packages (e.g., @modelcontextprotocol/server-filesystem)

## Documentation Maintenance

### README and CLI Test Script

The `README.md` file and `test-cli-examples.sh` script must be kept in sync. The test script verifies that all CLI examples documented in the README actually work as described. When updating CLI examples in the README:

1. Make corresponding updates to `test-cli-examples.sh`
2. Run the script to verify the examples work correctly
3. Ensure all CLI parameters match those available in `main.py`

Remember that tool arguments should be passed using the `--message` parameter, not `--args` (which doesn't exist in the implementation).

## Server Compatibility Notes

### Sequential Thinking Server

The Sequential Thinking MCP server (`@modelcontextprotocol/server-sequential-thinking`) uses the MCP sampling feature to request LLM completions from the client. For this server to work correctly:

1. The client must implement sampling callbacks to handle LLM completion requests
2. An actual LLM must be accessible to the client to generate responses

In our test environment, we can connect to the server and list tools, but tool execution that requires reasoning will fail without a proper sampling implementation. Claude Desktop handles these callbacks automatically when using this server.

### Playwright Server

The Playwright MCP server (`@executeautomation/playwright-mcp-server`) has a specific limitation:

1. It always binds to port 3001 regardless of configuration
2. This port binding is hardcoded in the server and cannot be changed
3. If port 3001 is already in use, the server will fail to start

Our client includes special handling to detect if port 3001 is already in use by a compatible MCP server (like one launched by Claude Desktop) and will connect to that existing server instead of launching a new one.