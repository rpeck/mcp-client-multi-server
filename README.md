# MCP Multi-Server Client

A Python client for connecting to multiple Model Context Protocol (MCP) servers simultaneously. This client is compatible with Claude Desktop's configuration format and supports various server types including Python scripts, Node.js applications, and npx packages.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Concepts and Architecture](#concepts-and-architecture)
  - [Transport Types](#transport-types)
  - [Server Lifecycle Management](#server-lifecycle-management)
  - [Server Registry and Error Reporting](#server-registry-and-error-reporting)
- [Configuration](#configuration)
- [Server Types](#server-types)
  - [General Server Types](#general-server-types)
  - [Specialized Servers](#specialized-servers)
  - [Required NPM Packages](#required-npm-packages)
  - [Custom Server Implementations](#custom-server-implementations)
- [Usage](#usage)
  - [Command Line Interface](#command-line-interface)
  - [Using as a Module](#using-as-a-module)
- [Development and Testing](#development-and-testing)
  - [Prerequisites](#prerequisites)
  - [Test Commands](#test-commands)
  - [Testing Coverage by Server Type](#testing-coverage-by-server-type)
  - [API Documentation Tests](#api-documentation-tests)
  - [Writing Custom Tests](#writing-custom-tests)
  - [TextContent Handling in Tests](#textcontent-handling-in-tests)
- [Included Examples](#included-examples)
- [Contributing](#contributing)
- [Future Development](#future-development)
  - [Transport and Protocol Support](#transport-and-protocol-support)
  - [Server Lifecycle Management](#server-lifecycle-management-1)
  - [Server Registry and Discovery](#server-registry-and-discovery)
  - [Additional Language Server Support](#additional-language-server-support)
  - [Extended API Support](#extended-api-support)
  - [CLI and User Experience](#cli-and-user-experience)
- [License](#license)

## Features

- **Multi-server support**: Connect to and manage multiple MCP servers from a single client
- **Claude Desktop compatibility**: Uses the same configuration format as Claude Desktop
- **Server launching**: Automatically launch local servers when needed
- **Enhanced transport support**: Flexible configuration for STDIO, WebSockets, SSE, Streamable HTTP transport types with comprehensive testing
- **Simple query interface**: Easy-to-use API for sending messages to specific servers
- **Tool discovery**: List available tools from each server
- **NPX server support**: Custom transport handling for npm-based MCP servers

## Installation

The project uses `uv` as the preferred package manager for faster and more reliable dependency management. You can install with either `uv` or traditional `pip`:

```bash
# Install from PyPI using uv (recommended)
uv pip install mcp-client-multi-server

# Install from PyPI using pip
pip install mcp-client-multi-server

# Or install from source with uv (recommended)
git clone https://github.com/yourusername/mcp-client-multi-server.git
cd mcp-client-multi-server
uv pip install -e .

# Or install from source with pip
git clone https://github.com/yourusername/mcp-client-multi-server.git
cd mcp-client-multi-server
pip install -e .
```

## Concepts and Architecture

### Transport Types

The MCP Multi-Server Client supports multiple transport types, each with different capabilities and use cases:

#### 1. STDIO Transport
- Direct communication through stdin/stdout pipes
- Used for local Python scripts, Node.js scripts, and NPX packages
- Simplest transport with no network requirements
- Example configuration:
```json
{
  "type": "stdio",
  "command": "python",
  "args": ["examples/multi_transport_echo.py", "--transport", "stdio"]
}
```

#### 2. WebSocket Transport
- Bidirectional communication over WebSocket protocol
- Supports secure (WSS) and non-secure (WS) connections
- Configurable with ping intervals, timeouts, and compression
- Example configuration:
```json
{
  "url": "wss://example.com/mcp/ws",
  "ws_config": {
    "ping_interval": 30.0,
    "ping_timeout": 10.0,
    "max_message_size": 1048576,
    "compression": true
  }
}
```

#### 3. Server-Sent Events (SSE) Transport
- HTTP-based protocol for server-to-client streaming
- Good for scenarios with mostly server-to-client communication
- Example configuration:
```json
{
  "type": "sse",
  "url": "https://example.com/mcp/sse"
}
```

#### 4. Streamable HTTP Transport
- HTTP-based transport with custom headers and timeout options
- Supports streaming responses
- Example configuration:
```json
{
  "type": "streamable-http",
  "url": "https://example.com/mcp/stream",
  "http_config": {
    "headers": {
      "Authorization": "Bearer token123",
      "Custom-Header": "Value"
    },
    "timeout": 60.0,
    "retry_count": 3,
    "retry_delay": 1.0
  }
}
```

All transport types are thoroughly tested in our test suite, with specific tests for each transport in `tests/test_echo_transports.py` and `tests/test_transports.py`.

### Server Lifecycle Management

The client includes intelligent server lifecycle management to handle different types of servers appropriately:

#### Server Types and Lifecycle

- **Local STDIO Servers**: Servers that rely on stdin/stdout pipes for communication (Python scripts, Node.js scripts, etc.) are automatically stopped when the client exits, unless specifically requested to keep running.

- **Socket-based Servers**: Servers that use Unix or TCP sockets for communication can remain running after the client exits and be reconnected to by future client instances.

- **Remote Servers**: For HTTP/WebSocket servers, the client only disconnects but never attempts to stop them.

#### Launch Methods

##### 1. Python Scripts
- Direct execution of Python scripts with the python interpreter
- Example: `"command": "python", "args": ["path/to/script.py"]`
- Supports environment variables and arguments

##### 2. Node.js Scripts
- Direct execution of JavaScript files with Node.js
- Example: `"command": "node", "args": ["path/to/script.js"]`

##### 3. NPX Packages
- Execution of npm packages without installation using npx
- Example: `"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]`
- `-y` flag automatically answers yes to installation prompts

##### 4. UVX Packages
- Python packages run through the UVX runner
- Example: `"command": "uvx", "args": ["mcp-server-fetch"]`
- Faster startup than traditional Python package installation

##### 5. Custom Executables
- Any executable available on the system path
- Example: `"command": "/path/to/custom/executable", "args": ["arg1", "arg2"]`

### Server Registry and Error Reporting

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
5. Surface error details when server launches fail

#### Server Error Debugging

When a server fails to start or crashes during initialization, the client provides detailed error feedback:

1. Error details from the server's stderr are captured and displayed
2. Output is directed to stderr when appropriate
3. Log file locations are provided for further investigation
4. Common issues like missing dependencies are clearly reported

All server output is logged to files in `~/.mcp-client-multi-server/logs/`:
- Each server has its own stdout and stderr log files
- Log files are named with server names and timestamps
- The most recent logs are shown when errors occur

Example error output:
```
Failed to launch server 'audio-interface'.

Error details:
ModuleNotFoundError: No module named 'pyaudio'

This may be caused by missing dependencies or configuration issues.
Full logs are available at: ~/.mcp-client-multi-server/logs/
```

For debugging, you can view all server logs with:
```bash
# List log files
ls -la ~/.mcp-client-multi-server/logs/

# View a specific log file
cat ~/.mcp-client-multi-server/logs/server-name_timestamp_stderr.log
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
    "websocket-server": {
      "url": "wss://example.com/mcp/ws",
      "ws_config": {
        "ping_interval": 30.0,
        "ping_timeout": 10.0,
        "max_message_size": 1048576,
        "compression": true
      }
    },
    "sse-server": {
      "type": "sse",
      "url": "https://example.com/mcp/sse"
    },
    "streamable-http-server": {
      "type": "streamable-http",
      "url": "https://example.com/mcp/stream",
      "http_config": {
        "headers": {
          "Authorization": "Bearer token",
          "X-API-Key": "api-key-value"
        }
      }
    }
  }
}
```

## Server Types

The client supports a variety of MCP server types, each with their own configuration and capabilities.

### General Server Types

- **Python scripts**: Run directly with Python
- **Node.js scripts**: Run with Node.js
- **NPX packages**: Run from npm registry without installation
- **UVX packages**: Run using the UVX package runner
- **Remote servers**: Connect via WebSockets or SSE

### Specialized Servers

#### Fetch Server

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

#### Sequential Thinking Server

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

**Important Note - Not Yet Fully Functional**: The Sequential Thinking server is currently **not fully functional** with this client implementation. The server requires MCP sampling callbacks to request LLM completions from the client, which this standalone client doesn't yet provide. When using the Sequential Thinking server:

- Basic connection and tool listing will work
- Tools that require LLM reasoning (most tools) will fail
- Full functionality requires an LLM-enabled client (like Claude Desktop)

We're working on implementing proper sampling callback support in a future release. For now, consider this server configuration as experimental.

#### Playwright Server

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

#### Filesystem Server

The filesystem server provides secure file system access within specified directories:

```json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allow"],
      "env": {}
    }
  }
}
```

The last argument specifies the root directory that the server is allowed to access. The server strictly enforces security, preventing access to any files or directories outside the allowed root path.

**Enhanced JSON Message Support:**
The client automatically parses JSON-formatted strings in the message parameter when querying this server:

```python
# These three formats are equivalent:

# Method 1: Using JSON string in message parameter (simplest for CLI)
client.query_server(server_name="filesystem", tool_name="list_directory", 
                   message='{"path": "/path/to/dir"}')

# Method 2: Using args dictionary
client.query_server(server_name="filesystem", tool_name="list_directory", 
                   args={"path": "/path/to/dir"})

# Method 3: Using direct keyword arguments
client.query_server(server_name="filesystem", tool_name="list_directory", 
                   path="/path/to/dir")
```

This flexibility allows you to use the most convenient format for your specific use case:
- JSON strings are ideal for CLI usage and when parameters are dynamically constructed
- Args dictionaries are useful when parameters are already in dictionary form
- Direct keyword arguments provide the cleanest code when hardcoded in Python

**Error Handling:**
The client provides enhanced error handling for filesystem operations, with detailed error messages when:
- Paths are outside the allowed directory
- Files or directories don't exist
- Permission issues occur
- JSON format errors are detected in message strings

**Known Limitations:**
- The current filesystem server version (2025.3.28) has issues with the `search_files` operation when using wildcard patterns (e.g., `*.txt`). When using wildcards, the operation may time out or return "No matches found" even when matching files exist. For reliable results, use exact filenames with the `search_files` operation or consider using `list_directory` as an alternative.
- The client automatically logs a warning when using wildcards with `search_files` and provides appropriate parameter mapping to work around these limitations.

### Required NPM Packages

To use npx-based MCP servers, the corresponding npm packages must be installed either globally or locally in your project:

```bash
# Install globally
npm install -g @modelcontextprotocol/server-filesystem

# Or install locally in your project
npm install @modelcontextprotocol/server-filesystem
```

The client will use `npx` to run these packages on demand. The `-y` flag in the configuration automatically answers "yes" to any installation prompts, but having the packages pre-installed ensures faster startup and avoids unexpected network requests.

### Custom Server Implementations

#### Multi-Transport Echo Server

The project includes a multi-transport echo server in `examples/multi_transport_echo.py` that can be configured to run with any of the supported transport types:

```bash
# Launch as a STDIO server
python examples/multi_transport_echo.py --transport stdio

# Launch as an SSE server
python examples/multi_transport_echo.py --transport sse --host localhost --port 8766

# Launch as a Streamable HTTP server
python examples/multi_transport_echo.py --transport streamable-http --host localhost --port 8767
```

This server is used extensively in our transport tests to verify consistent behavior across different transport protocols.

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

#### Server Lifecycle Commands

```bash
# Launch a server that will persist after client exit
python main.py -c config.json launch --server echo

# Stop a specific server
python main.py -c config.json stop --server echo

# Stop all running servers
python main.py -c config.json stop-all
```

#### Server-Specific Examples

Here are examples for different server types:

##### Echo Server

```bash
# List echo server tools
python main.py -c config.json tools --server echo

# Send a simple message to the echo server
python main.py -c config.json query --server echo --tool process_message --message "Hello world"

# Or use the default tool (also process_message) by omitting the --tool parameter
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

# Get detailed file information
python main.py -c config.json query --server filesystem --tool get_file_info --message '{"path": "/path/to/file.txt"}'

# Create a directory
python main.py -c config.json query --server filesystem --tool create_directory --message '{"path": "/path/to/new_dir"}'

# Show a recursive directory tree
python main.py -c config.json query --server filesystem --tool directory_tree --message '{"path": "/path/to/dir", "depth": 2}'

# Search for files - note: exact filenames work better than wildcards in current server version
python main.py -c config.json query --server filesystem --tool search_files --message '{"path": "/path/to/dir", "pattern": "example.txt"}'

# Alternative: List directory (more reliable than search with wildcards)
python main.py -c config.json query --server filesystem --tool list_directory --message '{"path": "/path/to/dir"}'

# View list of allowed directories (security boundaries)
python main.py -c config.json query --server filesystem --tool list_allowed_directories
```

The client provides enhanced error messages for common filesystem issues:

- Path access errors: "Access denied - path outside allowed directories: /etc not in /Users/username"
- File not found: "ENOENT: no such file or directory, open '/path/to/nonexistent.txt'"
- Directory not found: "ENOENT: no such file or directory, scandir '/path/to/nonexistent_dir'"
- Permission errors: "EACCES: permission denied, read '/path/to/protected_file'"

##### Fetch Server

The fetch server uses a default tool name of `fetch` (not `process_message`), which the client handles automatically:

```bash
# List fetch server tools
python main.py -c config.json tools --server fetch

# Fetch a web page (using message parameter)
# This automatically uses the 'fetch' tool instead of 'process_message'
python main.py -c config.json query --server fetch --message "https://example.com"

# Fetch a web page with JSON message containing URL
python main.py -c config.json query --server fetch --message '{"url": "https://example.com"}'

# Fetch with additional parameters in JSON
python main.py -c config.json query --server fetch --message '{
  "url": "https://example.com",
  "method": "GET",
  "headers": {"User-Agent": "MCP Client"}
}'
```

**Enhanced URL and JSON Parameter Handling:**

The client provides intelligent parameter handling for the fetch server:

1. **Simple URL Strings**: Pass a URL directly as the message parameter
   ```python
   client.query_server(server_name="fetch", message="https://example.com")
   ```

2. **JSON-formatted URLs**: Pass a JSON object with a URL and other parameters
   ```python
   client.query_server(server_name="fetch", message='{"url": "https://example.com", "method": "GET"}')
   ```

3. **Args Dictionary**: Use the args parameter to provide URL and other options
   ```python
   client.query_server(server_name="fetch", tool_name="fetch", args={"url": "https://example.com"})
   ```

All three methods work identically, providing flexibility based on your use case. The CLI automatically displays the URL being fetched for better user experience.
```

##### Sequential Thinking Server

**Note: The Sequential Thinking server is currently not fully functional with this client implementation.**

Currently, only basic connections and tool listing work reliably:

```bash
# List sequential-thinking server tools (this works)
python main.py -c config.json tools --server sequential-thinking

# View server information (this works)
python main.py -c config.json query --server sequential-thinking --tool server_info
```

The following example requires LLM sampling callbacks that are not yet supported, and will fail:

```bash
# NOT WORKING YET: Start a thinking sequence with first thought
# This requires LLM sampling support which is not yet implemented
python main.py -c config.json query --server sequential-thinking --tool sequentialthinking --message '{
  "thought": "First, I need to understand the problem...",
  "thoughtNumber": 1,
  "totalThoughts": 5,
  "nextThoughtNeeded": true
}'
```

We're working on implementing proper sampling callback support in a future release.

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

### Using as a Module

The MCP Multi-Server Client is designed to be easily integrated into other Python applications. This section covers key usage patterns for developers who want to use the client as a module.

#### Basic Usage

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

#### Advanced Usage with Custom Lifecycle Management

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

#### Working with Multiple Servers

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

#### Integration with Web Applications

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

#### Error Handling and Reconnection

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

## Development and Testing

The project includes comprehensive tests for all supported MCP server types and transport protocols. The test suite verifies server launching, connection handling, message processing, error reporting, and proper cleanup.

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

# Install sequential thinking server
npm install -g @modelcontextprotocol/server-sequential-thinking

# Install playwright server
npm install -g @executeautomation/playwright-mcp-server
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

# Run transport-specific tests
python -m pytest tests/test_echo_transports.py -v
python -m pytest tests/test_transports.py -v

# Run server-specific tests
python -m pytest tests/test_fetch_server.py -v
python -m pytest tests/test_sequential_thinking.py -v
python -m pytest tests/test_filesystem_server.py -v
python -m pytest tests/test_audio_interface.py -v
```

> **Note:** The test suite includes dedicated tests for NPX servers in `test_npx_servers.py`. These tests are more resilient and provide better diagnostics for NPX-related issues.

### Testing Coverage by Server Type

The test suite includes specific tests for each supported server type:

#### Basic Echo Server Tests (`test_servers.py`, `test_all_transports.py`)
- Connection establishment
- Server lifecycle (launch/stop)
- Tool listing
- Message processing
- Response validation

#### Multi-Transport Echo Tests (`test_echo_transports.py`)
- **STDIO Transport Testing**:
  * Connection establishment (`test_echo_stdio_connection`)
  * Ping functionality (`test_echo_stdio_ping`)
  * Message processing (`test_echo_stdio_process_message`)
  * Server info retrieval (`test_echo_stdio_server_info`)

- **SSE Transport Testing**:
  * Server launch (`test_echo_sse_server_launch`)
  * Client connection (`test_echo_sse_client_connection`)
  * Ping functionality (`test_echo_sse_ping`)
  * Message processing (`test_echo_sse_process_message`)

- **HTTP Streamable Transport Testing**:
  * Server launch (`test_echo_http_server_launch`)
  * Client connection (`test_echo_http_client_connection`)
  * Ping functionality (`test_echo_http_ping`)
  * Message processing (`test_echo_http_process_message`)
  * Custom headers handling (`test_echo_http_custom_headers`)

- **Multi-Transport Functionality**:
  * Running multiple transport types simultaneously (`test_run_all_transports_simultaneously`)
  * Verifying transport-specific response prefixes (`test_transport_specific_prefixes`)
  * TextContent response handling across all transport types

#### Fetch Server Tests (`test_fetch_server.py`)
- Server connection and launch/stop functionality
- Tool listing and validation
- URL fetching capabilities
- Response validation for web page content
- Auto-launch functionality
- Message shorthand syntax

#### Sequential Thinking Server Tests (`test_sequential_thinking.py`, `test_additional_servers.py`)
- Server connection capabilities
- Tool listing and verification
- Tool execution with parameter validation
- Server lifecycle management

#### Playwright Server Tests (`test_additional_servers.py`, `test_playwright_port_handling.py`)
- Connection to the server on port 3001
- Port 3001 availability checking and conflict resolution
- Tool listing functionality
- Basic tool execution
- Detection of existing MCP server on port 3001

#### Filesystem Server Tests (`test_filesystem_server.py`, `test_npx_servers.py`)
- Server launching and connection
- Tool listing and verification
- Directory listing functionality
- File operations testing

#### Audio Interface Server Tests (`test_audio_interface.py`)
- Configuration validation
- Server launch testing with dependency checking
- Log retrieval testing

#### Error Handling Tests (`test_error_handling.py`, `test_server_cleanup.py`)
- Server launch failure detection
- Error message reporting and validation
- Resource cleanup after server failures
- Log file creation and access

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

### TextContent Handling in Tests

When testing MCP servers that return TextContent objects (a common format in MCP responses), use the utility function pattern from `test_echo_transports.py`:

```python
def extract_text_content(response: Any) -> str:
    """Extract text from TextContent objects or convert response to string."""
    # Handle None case
    if response is None:
        return "None"
    
    # Handle list of TextContent objects
    if hasattr(response, '__iter__') and not isinstance(response, (str, dict)) and hasattr(response, '__len__'):
        if len(response) > 0 and all(hasattr(item, 'text') for item in response):
            return response[0].text
    # Handle single TextContent object
    elif hasattr(response, 'text'):
        return response.text
    # Handle dictionary with text field
    elif isinstance(response, dict) and 'text' in response:
        return response['text']
    # Default to string conversion
    return str(response)

# Usage in tests
response = await client.query_server(server_name="server", tool_name="tool")
response_text = extract_text_content(response)
assert "expected content" in response_text
```

## Included Examples

The project comes with example servers and configurations:

- `examples/echo_server.py`: A simple Python-based MCP server that echoes messages
- `examples/multi_transport_echo.py`: A server that can run with different transport types
- `examples/config.json`: Sample configuration file with multiple server types

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Future Development

The MCP Multi-Server Client has several potential areas for enhancement in future releases:

### Transport and Protocol Support

- **Streamable HTTP Transport**: Add support for the newer recommended transport that combines features of HTTP and SSE in a single endpoint
- **Enhanced WebSocket Support**: Upgrade our WebSocket implementation to be fully compliant with the latest MCP specification
- **Resumable Connections**: Support for resuming broken connections, especially for streaming transports
- **Session Management**: Improved session tracking and management across different transport types
- **Streaming Response Handling**: Better processing of partial/streaming responses from servers
- **Transport Auto-Discovery**: Develop smarter transport type detection based on server configuration and runtime behavior

### Server Lifecycle Management

- **Platform-specific Detachment**: Enhance platform-specific process detachment techniques, especially for macOS and Windows, to ensure servers persist reliably
- **Socket Path Detection**: Implement more sophisticated detection of socket-based servers vs pipe-based STDIO servers for more accurate lifecycle management
- **PID Validation**: Improve the accuracy of detecting existing server processes by considering additional metadata beyond just the PID
- **Socket Reconnection**: Enhance reconnection to servers that use STDIO over sockets or IPC, allowing true persistence across client sessions
- **Process Monitoring**: Add optional monitoring of server health with automatic recovery for critical servers

### Server Registry and Discovery

- **Server Discovery**: Add auto-discovery of running servers based on well-known socket paths or ports
- **Config Comparison**: Add validation to ensure server configs haven't changed before reusing an existing server
- **Remote Discovery**: Implement mechanisms to discover and connect to remote MCP servers
- **Capability-based Discovery**: Allow querying servers by their capabilities

### Additional Language Server Support

The client could be extended to support MCP servers written in other languages (in priority order):

1. **C#/.NET**: Support for Microsoft's C# implementation and Azure Functions-based MCP servers
2. **Java/Kotlin**: Support for the official Java SDK with Spring integration
3. **Go**: Support Go implementations (mcp-go, mcp-golang, Go-MCP)
4. **Rust**: Add support for Rust-based MCP servers (mcp_client_rs, mcp_rs, mcp-rust-sdk)
5. **Swift**: Add compatibility with the official Swift SDK for macOS/iOS integrations

### Extended API Support

- **Resources API**: Improve support for application-controlled data sources (Resources API)
- **Prompts API**: Add support for user-controlled templates (Prompts API)
- **OAuth Integration**: Add support for OAuth authentication flows for remote MCP servers
- **Cloud Provider Integration**: Add specific support for cloud-based MCP server platforms

### CLI and User Experience

- **Server Status**: Provide more detailed status information for each server, including uptime, client connections, and resource usage
- **Interactive Mode**: Add an interactive shell mode for the CLI for easier server management
- **Server Logs**: Provide commands to view, filter, and analyze server logs directly from the CLI
- **Multi-part Response Assembly**: Properly assemble and display multi-part streaming responses

## License

MIT