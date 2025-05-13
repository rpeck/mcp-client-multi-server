# MCP Multi-Server Client - Claude Instructions

## Key Information for Claude Code

This file contains instructions and information specifically for Claude Code to understand this project. For developer documentation, see README.md.

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

## Core Concepts

### Transport Types and Server Lifecycle

The client distinguishes between different transport types for server lifecycle management:

1. **Local STDIO Servers**: Servers that rely on stdin/stdout pipes for direct communication 
   - Python scripts, Node.js scripts, NPX packages
   - These are automatically stopped when the client exits (unless launched with the launch command)
   - Use `_is_local_stdio_server()` to identify these servers

2. **Socket-based Servers**: Servers using TCP or Unix sockets
   - Socket-based stdio servers and servers with a URL/port
   - These are never automatically stopped by default, as they can operate independently

3. **Remote Servers**: External servers accessed via HTTP, WebSockets, etc.
   - Only disconnected from, never stopped

### Server Registry

The client tracks running servers in `~/.mcp-client-multi-server/servers.json`:
- Contains PIDs, log locations, start times, and config hashes
- Enables reconnection to existing servers across client instances

### Critical Methods

- `_is_local_stdio_server()`: Determines if a server is a pipe-based STDIO server
- `stop_local_stdio_servers()`: Stops only STDIO servers that rely on pipes
- `close(stop_servers=True)`: Closes connections and optionally stops STDIO servers
- `launch_server()`: Launches and detaches a server process