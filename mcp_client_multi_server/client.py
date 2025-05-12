"""
MultiServerClient - Multi-server MCP client compatible with Claude Desktop configs.
"""

import os
import json
import logging
import asyncio
import subprocess
import shlex
import signal
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable, Awaitable, TypedDict, Set

from fastmcp import Client
from fastmcp.client.transports import infer_transport, ClientTransport, PythonStdioTransport, NodeStdioTransport, NpxStdioTransport, StdioTransport


class NpxProcessTransport(StdioTransport):
    """
    Custom transport for running npx packages as MCP servers.

    This handles the execution of npx commands properly, working around
    limitations in FastMCP's built-in transports when dealing with npx.
    """

    def __init__(
        self,
        npx_path: str,
        package: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize a transport for an npx-based MCP server.

        Args:
            npx_path: Path to the npx executable
            package: NPM package name to execute
            args: Additional arguments to pass to the package
            env: Environment variables to set for the process
        """
        self.npx_path = npx_path
        self.package = package
        self.server_args = args or []

        # Build the command and arguments to execute
        command = npx_path
        transport_args = ["-y", package] + self.server_args

        # Initialize the StdioTransport base class with the correct signature
        super().__init__(command=command, args=transport_args, env=env or {})


class UvxProcessTransport(StdioTransport):
    """
    Custom transport for running uvx packages as MCP servers.

    This handles the execution of uvx commands properly, similar to
    NpxProcessTransport but for Python-based UVX packages.
    """

    def __init__(
        self,
        uvx_path: str,
        package: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize a transport for a uvx-based MCP server.

        Args:
            uvx_path: Path to the uvx executable
            package: Package name to execute (e.g., mcp-server-fetch)
            args: Additional arguments to pass to the package
            env: Environment variables to set for the process
        """
        self.uvx_path = uvx_path
        self.package = package
        self.server_args = args or []

        # Build the command and arguments to execute
        command = uvx_path
        transport_args = [package] + self.server_args

        # Initialize the StdioTransport base class with the correct signature
        super().__init__(command=command, args=transport_args, env=env or {})


# Type definitions
class ServerConfig(TypedDict, total=False):
    url: Optional[str]
    type: str
    command: str
    args: List[str]
    env: Dict[str, str]


class Config(TypedDict):
    mcpServers: Dict[str, ServerConfig]


class MultiServerClient:
    """
    A multi-server MCP client that can use multiple different MCP servers.
    Compatible with Claude Desktop's configuration format.
    """

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        custom_config: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
        auto_launch: bool = True,
    ):
        """
        Initialize the Multi-Server MCP client.

        Args:
            config_path: Path to a Claude Desktop compatible config file.
                         If None, will look in default locations.
            custom_config: Alternatively, provide config directly as a dict.
            logger: Optional logger to use.
            auto_launch: Automatically launch local servers when needed.
        """
        self.logger = logger or logging.getLogger("mcp_client_multi_server")
        self._clients: Dict[str, Client] = {}
        self._config: Config = {"mcpServers": {}}
        self._active_connections: Dict[str, Any] = {}
        self._local_processes: Dict[str, subprocess.Popen] = {}
        self._auto_launch: bool = auto_launch
        self._launched_servers: Set[str] = set()

        # Load configuration
        if custom_config:
            self._config = custom_config
        elif config_path:
            self._load_config(config_path)
        else:
            self._load_default_config()

        # Initialize servers registry
        self._init_server_registry()

    def _load_config(self, config_path: Union[str, Path]) -> None:
        """Load configuration from a specified file path."""
        path = Path(config_path)
        if not path.exists():
            self.logger.warning(f"Config file not found: {path}")
            return

        try:
            with open(path, "r") as f:
                self._config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Failed to load config file: {e}")

    def _load_default_config(self) -> None:
        """
        Load configuration from default Claude Desktop locations.
        """
        # Default locations for Claude Desktop config
        home = Path.home()
        
        if os.name == "posix":  # macOS/Linux
            default_path = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        else:  # Windows
            appdata = os.environ.get("APPDATA", "")
            default_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
        
        if default_path.exists():
            self._load_config(default_path)
        else:
            self.logger.warning(f"No config found at default location: {default_path}")

    def _init_server_registry(self) -> None:
        """Initialize server registry from config."""
        for server_name, server_config in self._config.get("mcpServers", {}).items():
            self.logger.info(f"Registering MCP server: {server_name}")
            # We don't create clients yet, just register the configuration
            pass

    def list_servers(self) -> List[str]:
        """List all configured server names."""
        return list(self._config.get("mcpServers", {}).keys())

    def get_server_config(self, server_name: str) -> Optional[ServerConfig]:
        """Get configuration for a specific server."""
        return self._config.get("mcpServers", {}).get(server_name)

    def add_server(self, server_name: str, server_config: ServerConfig) -> None:
        """Add a new server to the configuration."""
        if "mcpServers" not in self._config:
            self._config["mcpServers"] = {}
        self._config["mcpServers"][server_name] = server_config
        self.logger.info(f"Added server configuration: {server_name}")

    async def connect(self, server_name: str, launch_if_needed: bool = None) -> Optional[Client]:
        """
        Connect to a specific MCP server by name.

        Args:
            server_name: Name of the server to connect to
            launch_if_needed: Launch the server if it's not already running.
                              If None, uses the client's auto_launch setting.

        Returns:
            Connected FastMCP client or None if connection failed
        """
        if server_name in self._clients:
            self.logger.info(f"Already have client for {server_name}")
            return self._clients[server_name]

        server_config = self.get_server_config(server_name)
        if not server_config:
            self.logger.error(f"No configuration found for server: {server_name}")
            return None

        try:
            # Special handling for Playwright server
            # If it's configured as stdio but port 3001 is already in use,
            # assume it's Claude Desktop running it and switch to HTTP mode
            if (server_name == "playwright" and
                server_config.get("type") == "stdio" and
                "@executeautomation/playwright-mcp-server" in str(server_config.get("args", []))):

                # Check if port 3001 is in use
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                port_in_use = sock.connect_ex(('localhost', 3001)) == 0
                sock.close()

                if port_in_use:
                    self.logger.info("Detected Playwright server already running on port 3001, using HTTP connection")

                    # Test if the server at port 3001 is a valid MCP server
                    # by making a quick request to the server_info endpoint
                    import http.client
                    import json
                    try:
                        conn = http.client.HTTPConnection("localhost", 3001)
                        conn.request("GET", "/mcp/server_info")
                        response = conn.getresponse()

                        if response.status == 200:
                            server_info = json.loads(response.read().decode())
                            if "name" in server_info and "playwright" in server_info["name"].lower():
                                self.logger.info(f"Verified Playwright MCP server at port 3001: {server_info['name']}")
                            else:
                                self.logger.warning(f"Server at port 3001 does not appear to be a Playwright MCP server: {server_info.get('name', 'unknown')}")
                                # We'll still try to use it, but warn the user
                        else:
                            self.logger.warning(f"Server at port 3001 returned status {response.status}, may not be a valid MCP server")
                            # Since the port is in use but is not a valid MCP server, we can't proceed
                            # Playwright server is hardcoded to use port 3001 and can't be changed
                            self.logger.error(
                                "Port 3001 is in use but is not a valid Playwright MCP server. "
                                "The Playwright server requires port 3001 to be available. "
                                "Please stop any other services using this port before launching the Playwright server."
                            )
                            return None
                    except Exception as e:
                        self.logger.warning(f"Failed to verify MCP server at port 3001: {e}")
                        # Since verification failed and port is in use, we can't proceed
                        self.logger.error(
                            f"Port 3001 is in use and verification failed: {e}. "
                            "The Playwright server requires port 3001 to be available. "
                            "Please stop any other services using this port before launching the Playwright server."
                        )
                        return None

                    # Create a temp config with HTTP URL instead of trying to launch
                    http_config = {"url": "http://localhost:3001"}
                    transport = self._create_transport_from_config(server_name, http_config)
                    client = Client(transport)
                    self._clients[server_name] = client
                    return client

            # Regular handling for other servers
            # First, check if we need to launch a local server
            should_launch = launch_if_needed if launch_if_needed is not None else self._auto_launch
            if should_launch and self._is_launchable(server_config) and server_name not in self._launched_servers:
                success = await self.launch_server(server_name)
                if not success:
                    self.logger.error(f"Failed to launch server {server_name}")
                    return None
                self._launched_servers.add(server_name)

            # Create a client based on the server configuration
            transport = self._create_transport_from_config(server_name, server_config)
            client = Client(transport)
            self._clients[server_name] = client
            return client
        except Exception as e:
            self.logger.error(f"Failed to connect to server {server_name}: {e}")
            return None

    def _create_transport_from_config(
        self, server_name: str, config: ServerConfig
    ) -> ClientTransport:
        """
        Create an appropriate transport from server configuration.
        
        Args:
            server_name: Name of the server
            config: Server configuration dictionary
            
        Returns:
            Configured ClientTransport instance
        """
        # If URL is provided, let infer_transport handle it
        if "url" in config:
            return infer_transport(config["url"])
            
        # Handle stdio transport (most common in Claude Desktop)
        if config.get("type") == "stdio":
            # We create an appropriate transport based on the command
            cmd = config.get("command", "")
            args = config.get("args", [])
            env = config.get("env", {})
            
            # Construct a command string that FastMCP can use
            # This depends on the command type (python, node, etc.)
            if cmd == "python":
                script_path = args[0] if args else ""
                remaining_args = args[1:] if len(args) > 1 else []
                return PythonStdioTransport(
                    script_path=script_path, 
                    args=remaining_args,
                    env=env, 
                    python_cmd=cmd
                )
            elif cmd == "node":
                script_path = args[0] if args else ""
                remaining_args = args[1:] if len(args) > 1 else []
                return NodeStdioTransport(
                    script_path=script_path, 
                    args=remaining_args,
                    env=env, 
                    node_cmd=cmd
                )
            elif "npx" in cmd or cmd.endswith("npx"):
                # For npx-based servers, use our custom transport
                self.logger.info(f"Using custom NpxProcessTransport for npx command: {cmd}")

                # The first argument is the package name
                if not args:
                    raise ValueError(f"No package specified for npx command: {cmd}")

                # Check if -y is already included
                if "-y" in args:
                    # Extract the npx_args (includes -y)
                    npx_args_end_idx = args.index("-y") + 1
                    
                    # The package name follows the npx_args
                    package = args[npx_args_end_idx]
                    
                    # Any remaining args are server args
                    server_args = args[npx_args_end_idx + 1:] if len(args) > npx_args_end_idx + 1 else []
                else:
                    # No npx args, first arg is package
                    package = args[0]
                    server_args = args[1:] if len(args) > 1 else []
                
                self.logger.info(f"Creating NpxProcessTransport with: package={package}, server_args={server_args}")
                
                # Use our custom NpxProcessTransport for npx commands
                return NpxProcessTransport(
                    npx_path=cmd,
                    package=package,
                    args=server_args,
                    env=env
                )
            elif "uvx" in cmd or cmd.endswith("uvx"):
                # Handle uvx-based packages with our custom transport
                self.logger.info(f"Creating transport for uvx command: {cmd}")

                # The first argument is the package name
                if not args:
                    raise ValueError(f"No package specified for uvx command: {cmd}")

                package = args[0]
                server_args = args[1:] if len(args) > 1 else []

                self.logger.info(f"Creating UvxProcessTransport with: package={package}, server_args={server_args}")

                # Use our custom UvxProcessTransport for uvx commands
                return UvxProcessTransport(
                    uvx_path=cmd,
                    package=package,
                    args=server_args,
                    env=env
                )
            # Handle case where server has a runtime field (like the playwright server)
            elif config.get("runtime") == "node" and "npx" in cmd:
                self.logger.info(f"Creating transport for node runtime npx command: {cmd}")

                # The package is still specified in args
                if not args:
                    raise ValueError(f"No package specified for npx command: {cmd}")

                # Check if -y is already included
                if "-y" in args:
                    # Extract the npx_args (includes -y)
                    npx_args_end_idx = args.index("-y") + 1

                    # The package name follows the npx_args
                    package = args[npx_args_end_idx]

                    # Any remaining args are server args
                    server_args = args[npx_args_end_idx + 1:] if len(args) > npx_args_end_idx + 1 else []
                else:
                    # No npx args, first arg is package
                    package = args[0]
                    server_args = args[1:] if len(args) > 1 else []

                self.logger.info(f"Creating Node Runtime NpxProcessTransport with: package={package}, server_args={server_args}")

                # Use our custom NpxProcessTransport for node runtime npx commands
                return NpxProcessTransport(
                    npx_path=cmd,
                    package=package,
                    args=server_args,
                    env=env
                )
            else:
                # Generic approach for other commands
                full_cmd = [cmd] + args
                cmd_str = " ".join(full_cmd)
                return infer_transport(cmd_str)
                
        # Fallback
        raise ValueError(f"Unsupported server configuration for {server_name}")
        
    def _is_launchable(self, config: ServerConfig) -> bool:
        """Determine if a server configuration is launchable as a local process."""
        # Only stdio transports with a command can be launched
        return config.get("type") == "stdio" and "command" in config

    async def query_server(
        self, server_name: str, message: str = None, tool_name: str = "process_message", args: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Send a query to a specific server.

        Args:
            server_name: Name of the server to query
            message: Message to send (optional, depends on tool)
            tool_name: Name of the tool to call (default: process_message)
            args: Additional arguments to pass to the tool (optional)

        Returns:
            Response string or None if failed
        """
        client = await self.connect(server_name)
        if not client:
            return None

        try:
            async with client:
                # First check if the tool exists
                tools = await client.list_tools()
                tool_names = [tool.name for tool in tools]

                if tool_name not in tool_names:
                    self.logger.error(
                        f"Tool '{tool_name}' not found on server {server_name}. "
                        f"Available tools: {tool_names}"
                    )
                    return None

                # Call the specified tool with the appropriate arguments
                # Start with provided args or empty dict
                tool_args = args.copy() if args else {}

                # Special handling for fetch server
                if server_name == "fetch" and tool_name == "fetch":
                    # For fetch server, url is the main parameter
                    if message is not None:
                        # Add URL to tool_args or override if already present
                        tool_args["url"] = message
                        self.logger.info(f"Setting URL parameter for fetch server: {message}")
                # Regular handling for message parameter
                elif message is not None:
                    # Only set message parameter if not already in tool_args
                    if "message" not in tool_args:
                        tool_args["message"] = message

                # Call the tool with the combined arguments
                self.logger.debug(f"Calling tool {tool_name} with args: {tool_args}")
                response = await client.call_tool(tool_name, tool_args)
                return response
        except Exception as e:
            self.logger.error(f"Error querying server {server_name}: {e}")
            return None

    async def launch_server(self, server_name: str) -> bool:
        """Launch a local server process based on configuration.

        Args:
            server_name: Name of the server to launch

        Returns:
            True if server was successfully launched, False otherwise
        """
        config = self.get_server_config(server_name)
        if not config:
            self.logger.error(f"No configuration found for server: {server_name}")
            return False

        if not self._is_launchable(config):
            self.logger.error(f"Server {server_name} is not launchable (not a stdio server)")
            return False

        # Only launch if not already running
        if server_name in self._local_processes and self._local_processes[server_name].poll() is None:
            self.logger.info(f"Server {server_name} is already running")
            return True

        # Build the command
        cmd = config.get("command")
        args = config.get("args", [])
        env_vars = config.get("env", {})

        # Create environment with parent env plus config env vars
        env = os.environ.copy()

        # Convert all env values to strings (subprocess requires string values)
        string_env_vars = {k: str(v) for k, v in env_vars.items()}
        env.update(string_env_vars)

        # Special handling for Playwright server
        if server_name == "playwright" and "@executeautomation/playwright-mcp-server" in str(args):
            # Check if port 3001 is already in use
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', 3001))
                sock.close()

                if result == 0:  # Port is in use
                    self.logger.error(
                        "Port 3001 is already in use. The Playwright server requires port 3001 to be available. "
                        "Please stop any other services using this port before launching the Playwright server."
                    )
                    return False
            except Exception as e:
                self.logger.warning(f"Failed to check port status: {e}")

        try:
            # Construct full command
            full_cmd = [cmd] + args
            self.logger.info(f"Launching server {server_name}: {' '.join(full_cmd)}")

            # Launch process
            process = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=0,  # Unbuffered
            )

            # Store the process
            self._local_processes[server_name] = process

            # Give it a moment to start up
            await asyncio.sleep(1)

            # Check if the process is still running
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else "No error output"
                self.logger.error(f"Server {server_name} failed to start. Exit code: {process.returncode}\nError: {stderr}")
                return False

            self.logger.info(f"Successfully launched server {server_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error launching server {server_name}: {e}")
            return False
            
    async def stop_server(self, server_name: str) -> bool:
        """Stop a running local server process.
        
        Args:
            server_name: Name of the server to stop
            
        Returns:
            True if server was successfully stopped, False otherwise
        """
        if server_name not in self._local_processes:
            self.logger.warning(f"Server {server_name} is not running as a local process")
            return False
            
        process = self._local_processes[server_name]
        if process.poll() is not None:
            # Process already stopped
            self._local_processes.pop(server_name)
            return True
            
        try:
            # First try to terminate gracefully
            self.logger.info(f"Stopping server {server_name}")
            
            if sys.platform == "win32":
                process.terminate()
            else:
                # Send SIGTERM
                process.send_signal(signal.SIGTERM)
                
            # Wait up to 5 seconds for the process to terminate
            for _ in range(10):
                await asyncio.sleep(0.5)
                if process.poll() is not None:
                    break
                    
            # If it's still running, force kill
            if process.poll() is None:
                self.logger.warning(f"Server {server_name} didn't terminate gracefully, forcing kill")
                process.kill()
                await asyncio.sleep(0.5)
                
            # Clean up
            self._local_processes.pop(server_name)
            if server_name in self._launched_servers:
                self._launched_servers.remove(server_name)
                
            self.logger.info(f"Server {server_name} stopped")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping server {server_name}: {e}")
            return False
            
    async def list_server_tools(self, server_name: str) -> Optional[List[dict]]:
        """
        List all available tools on a specific server.
        
        Args:
            server_name: Name of the server to query
            
        Returns:
            List of tool information dictionaries or None if connection failed
        """
        client = await self.connect(server_name)
        if not client:
            return None
            
        try:
            async with client:
                tools = await client.list_tools()
                tool_info = []
                for tool in tools:
                    # Convert tool to dict with relevant information
                    info = {
                        "name": tool.name,
                        "description": getattr(tool, "description", ""),
                        "parameters": getattr(tool, "parameters", {}),
                    }
                    tool_info.append(info)
                return tool_info
        except Exception as e:
            self.logger.error(f"Error listing tools on server {server_name}: {e}")
            return None
            
    # Code for the _launch_playwright_on_alternate_port method was removed
    # because we discovered that the Playwright server is hardcoded to always
    # use port 3001 and ignores any port setting environments.

    async def close(self) -> None:
        """Close all client connections and stop local servers."""
        # First close client connections
        for server_name, client in self._clients.items():
            try:
                # Check if client has an active connection
                if hasattr(client, "_session") and client._session:
                    await client._session.close()
                self.logger.info(f"Closed connection to {server_name}")
            except Exception as e:
                self.logger.error(f"Error closing connection to {server_name}: {e}")

        self._clients.clear()

        # Close any temporary clients created for alternate ports
        if hasattr(self, "_temp_clients"):
            for temp_client in self._temp_clients:
                await temp_client.close()
            self._temp_clients = []

        # Then stop local server processes
        server_names = list(self._local_processes.keys())
        for server_name in server_names:
            await self.stop_server(server_name)

    async def __aenter__(self):
        """Context manager support."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure all connections are closed when exiting context."""
        await self.close()