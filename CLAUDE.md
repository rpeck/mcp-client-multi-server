# MCP Multi-Server Client - Claude Instructions

## Key Information for Claude Code

This file contains instructions and information specifically for Claude Code to understand this project. For developer documentation, see README.md.

## Package Management

This project uses [uv](https://github.com/astral-sh/uv) as the package manager for improved installation speed and dependency resolution. The project is configured for uv through the `pyproject.toml` file, which specifies dependencies and Python version requirements.

To install dependencies with uv:
```bash
# Install required dependencies
uv pip install -e .

# Install development dependencies
uv pip install -e ".[dev]"
```

When making changes that affect dependencies:
1. Update the dependencies in `pyproject.toml`
2. Run `uv pip install -e .` to update the environment
3. Ensure the `uv.lock` file is committed to version control

## Documentation and Test Synchronization

**IMPORTANT**: The API examples in the README.md file have corresponding test cases in `tests/test_module_integration_examples.py`. When updating the README examples, always make corresponding updates to the tests to ensure they stay in sync.

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
4. Update examples in this file if applicable

The tests include verification for all major usage patterns documented in the README:
- Basic client usage
- Advanced usage with custom lifecycle management
- Working with multiple servers
- Web application integration
- Error handling and reconnection strategies

## Testing Infrastructure

The project includes comprehensive tests for all supported server types and transport protocols. This is critical for ensuring reliability across different MCP implementations.

### Server-Specific Tests

Each supported server type has dedicated tests:

1. **Basic Echo Server**: `tests/test_servers.py`, `tests/test_all_transports.py`
   - Tests basic server operations and message handling
   - Used as the baseline for server functionality tests

2. **Multi-Transport Echo Servers**:
   - `tests/test_echo_transports.py`: Tests all transport types
   - **STDIO Transport**: Full request/response cycle
     * Connection, ping, message processing, server info
   - **SSE Transport**: Server-sent events handling
     * Server launch, client connection, ping, message processing
   - **HTTP Streamable Transport**: HTTP-based communication
     * Server launch, client connection, ping, message processing, custom headers
   - **Multi-Transport**: Running multiple transport types simultaneously
   - Includes testing for TextContent response handling and proper parsing

3. **Fetch Server**: `tests/test_fetch_server.py`
   - Tests URL fetching capabilities and response handling
   - Verifies both auto-launch and explicit launch behaviors

4. **Sequential Thinking Server**: `tests/test_sequential_thinking.py`, `tests/test_additional_servers.py`
   - Tests connection and tool discovery
   - Tool execution tests with xfail for features requiring LLM callbacks

5. **Playwright Server**: `tests/test_additional_servers.py`, `tests/test_playwright_port_handling.py`
   - Tests port 3001 handling and conflict resolution
   - Verifies tool discovery and execution

6. **Filesystem Server**: `tests/test_filesystem_server.py`, `tests/test_npx_servers.py`
   - Tests NPX-based server launching
   - Verifies filesystem operations and tool discovery

7. **Audio Interface Server**: `tests/test_audio_interface.py`
   - Tests configuration validation
   - Tests error reporting for missing dependencies
   - Tests log file management

### Error Handling Tests

Some tests specifically verify the error handling and reporting capabilities:

- `tests/test_error_handling.py`: Tests proper error reporting during server startup failures
- `tests/test_server_cleanup.py`: Tests resource cleanup after server failures

### Testing Utilities

Common test patterns include:

```python
# Extract text from TextContent objects (common in MCP responses)
def extract_text_content(response):
    # Handle None case
    if response is None:
        return "None"
    
    # Handle list of TextContent objects
    if hasattr(response, '__iter__') and not isinstance(response, (str, dict)):
        if len(response) > 0 and all(hasattr(item, 'text') for item in response):
            return response[0].text
    # Handle single TextContent object
    elif hasattr(response, 'text'):
        return response.text
    # Default to string conversion
    return str(response)
```

### Running Tests

To run different test groups:

```bash
# Run all tests
python run_tests.py

# Run only server tests
python -m pytest tests/test_*_server*.py -v

# Run only transport tests
python -m pytest tests/test_*_transport*.py -v

# Run specific server tests
python -m pytest tests/test_echo_transports.py -v
python -m pytest tests/test_sequential_thinking.py -v
```

## Core Concepts

### Transport Types and Server Lifecycle

The client supports multiple transport types with configurable options, all thoroughly tested:

1. **Local STDIO Servers**: Servers that rely on stdin/stdout pipes for direct communication
   - Python scripts, Node.js scripts, NPX packages
   - These are automatically stopped when the client exits (unless launched with the launch command)
   - Use `_is_local_stdio_server()` to identify these servers
   - Tested in `tests/test_echo_transports.py::TestEchoStdio`

2. **Socket-based Servers**: Servers using TCP or Unix sockets
   - Socket-based stdio servers and servers with a URL/port
   - These are never automatically stopped by default, as they can operate independently

3. **Remote Servers**: External servers accessed via various transport protocols:
   - **WebSocket Servers**: Configurable with custom ping intervals, timeouts, and compression
   - **SSE Servers**: Server-sent events transport for streaming responses
     - Tested in `tests/test_echo_transports.py::TestEchoSse`
   - **Streamable HTTP Servers**: HTTP-based transport with custom headers and timeout options
     - Tested in `tests/test_echo_transports.py::TestEchoHttp`
   - Only disconnected from, never stopped

### Transport Testing Infrastructure

Each transport type has dedicated tests:

1. **STDIO Transport Tests**:
   - Connection establishment (`test_echo_stdio_connection`)
   - Ping functionality (`test_echo_stdio_ping`)
   - Message processing (`test_echo_stdio_process_message`)
   - Server info retrieval (`test_echo_stdio_server_info`)

2. **SSE Transport Tests**:
   - Server launch (`test_echo_sse_server_launch`)
   - Client connection (`test_echo_sse_client_connection`)
   - Ping functionality (`test_echo_sse_ping`)
   - Message processing (`test_echo_sse_process_message`)

3. **HTTP Streamable Transport Tests**:
   - Server launch (`test_echo_http_server_launch`)
   - Client connection (`test_echo_http_client_connection`)
   - Ping functionality (`test_echo_http_ping`)
   - Message processing (`test_echo_http_process_message`)
   - Custom headers handling (`test_echo_http_custom_headers`)

4. **Multi-Transport Tests**:
   - Running multiple transports simultaneously (`test_run_all_transports_simultaneously`)
   - Transport-specific prefixes (`test_transport_specific_prefixes`)

All tests validate proper connection, message exchange, and server lifecycle management for each transport.

### Transport Configuration

The client supports detailed transport configuration through the config file:

```json
{
  "mcpServers": {
    "websocket-server": {
      "url": "wss://example.com/mcp/ws",
      "ws_config": {
        "ping_interval": 30.0,
        "ping_timeout": 10.0,
        "max_message_size": 1048576,
        "compression": true
      }
    },
    "http-server": {
      "url": "https://example.com/mcp/http",
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
  }
}
```

### Server Registry and Error Handling

The client tracks running servers in `~/.mcp-client-multi-server/servers.json`:
- Contains PIDs, log locations, start times, and config hashes
- Enables reconnection to existing servers across client instances
- Provides access to logs for debugging server failures

#### Error Reporting System

The client has a robust error reporting system for server launches that is thoroughly tested in `tests/test_error_handling.py` and `tests/test_audio_interface.py`:

- Each server's stdout and stderr is captured to log files in `~/.mcp-client-multi-server/logs/`
- Log files use a naming pattern of `{server_name}_{timestamp}_{stdout|stderr}.log`
- When a server fails to start, the error details from stderr are extracted and displayed
- Error messages are directed to stderr and include helpful diagnostic information
- The `get_server_logs()` method retrieves paths to a server's log files by checking:
  1. Current running processes with log path attributes
  2. Server registry entries for previously launched servers
  3. Log directory for any logs matching the server name pattern

#### Error Handling Tests

The error handling system is verified by tests that intentionally create failure conditions:

- Missing dependencies (e.g., audio-interface server without pyaudio)
- Invalid configuration parameters
- Server startup errors
- Resource cleanup after failures

These tests ensure that when a server fails to start or crashes during initialization, useful error information is provided to the user.

### Critical Methods

- `_is_local_stdio_server()`: Determines if a server is a pipe-based STDIO server
- `stop_local_stdio_servers()`: Stops only STDIO servers that rely on pipes 
- `close(stop_servers=True)`: Closes connections and optionally stops STDIO servers
- `launch_server()`: Launches and detaches a server process
- `get_server_logs()`: Retrieves paths to a server's log files for debugging