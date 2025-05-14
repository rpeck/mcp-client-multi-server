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
import time
import socket
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable, Awaitable, TypedDict, Set, Tuple

from fastmcp import Client
from fastmcp.client.transports import (
    infer_transport, ClientTransport, PythonStdioTransport,
    NodeStdioTransport, NpxStdioTransport, StdioTransport,
    WSTransport, SSETransport, StreamableHttpTransport
)


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
class WebSocketConfig(TypedDict, total=False):
    """WebSocket-specific configuration options."""
    ping_interval: float  # In seconds, how often to send WebSocket ping frames
    ping_timeout: float   # In seconds, how long to wait for a pong response
    max_message_size: int  # Maximum size of a WebSocket message in bytes
    close_timeout: float  # In seconds, how long to wait for a clean WebSocket close
    compression: bool  # Whether to use per-message deflate compression


class StreamableHttpConfig(TypedDict, total=False):
    """Streamable HTTP-specific configuration options."""
    headers: Dict[str, str]  # Custom HTTP headers to include with requests
    timeout: float  # Request timeout in seconds
    retry_count: int  # Number of times to retry failed requests
    retry_delay: float  # Delay between retries in seconds


class ServerConfig(TypedDict, total=False):
    url: Optional[str]
    type: str
    command: str
    args: List[str]
    env: Dict[str, str]
    ws_config: WebSocketConfig  # Optional WebSocket-specific configuration
    http_config: StreamableHttpConfig  # Optional Streamable HTTP-specific configuration


class Config(TypedDict):
    mcpServers: Dict[str, ServerConfig]


class ServerInfo:
    """Class to store and track information about running servers."""

    def __init__(
        self,
        server_name: str,
        pid: Optional[int] = None,
        start_time: Optional[float] = None,
        config_hash: Optional[str] = None,
        log_dir: Optional[Path] = None,
        stdout_log: Optional[Path] = None,
        stderr_log: Optional[Path] = None
    ):
        self.server_name = server_name
        self.pid = pid
        self.start_time = start_time or time.time()
        self.config_hash = config_hash
        self.log_dir = log_dir
        self.stdout_log = stdout_log
        self.stderr_log = stderr_log

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "server_name": self.server_name,
            "pid": self.pid,
            "start_time": self.start_time,
            "config_hash": self.config_hash,
            "log_dir": str(self.log_dir) if self.log_dir else None,
            "stdout_log": str(self.stdout_log) if self.stdout_log else None,
            "stderr_log": str(self.stderr_log) if self.stderr_log else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServerInfo':
        """Create from dictionary after deserialization."""
        return cls(
            server_name=data["server_name"],
            pid=data.get("pid"),
            start_time=data.get("start_time"),
            config_hash=data.get("config_hash"),
            log_dir=Path(data["log_dir"]) if data.get("log_dir") else None,
            stdout_log=Path(data["stdout_log"]) if data.get("stdout_log") else None,
            stderr_log=Path(data["stderr_log"]) if data.get("stderr_log") else None
        )


class MultiServerClient:
    """
    A multi-server MCP client that can use multiple different MCP servers.
    Compatible with Claude Desktop's configuration format.
    """

    # Directory for server tracking and logs
    SERVER_TRACKING_DIR = Path.home() / ".mcp-client-multi-server"
    SERVER_REGISTRY_FILE = SERVER_TRACKING_DIR / "servers.json"
    LOG_DIR = SERVER_TRACKING_DIR / "logs"

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
        self.config_path = config_path

        # Ensure server tracking directory exists
        self.SERVER_TRACKING_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Load configuration
        if custom_config:
            self._config = custom_config
        elif config_path:
            self._load_config(config_path)
        else:
            self._load_default_config()

        # Initialize servers registry
        self._init_server_registry()

        # Load existing server registry
        self._server_registry = self._load_server_registry()

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

    def _load_server_registry(self) -> Dict[str, ServerInfo]:
        """Load the server registry from the persistent storage file."""
        registry = {}
        if self.SERVER_REGISTRY_FILE.exists():
            try:
                with open(self.SERVER_REGISTRY_FILE, 'r') as f:
                    data = json.load(f)
                    for server_name, server_data in data.items():
                        registry[server_name] = ServerInfo.from_dict(server_data)
                self.logger.info(f"Loaded server registry with {len(registry)} entries")
            except Exception as e:
                self.logger.error(f"Error loading server registry: {e}")
        return registry

    def _save_server_registry(self) -> None:
        """Save the server registry to persistent storage."""
        try:
            registry_data = {
                name: info.to_dict() for name, info in self._server_registry.items()
            }
            with open(self.SERVER_REGISTRY_FILE, 'w') as f:
                json.dump(registry_data, f, indent=2)
            self.logger.debug(f"Saved server registry with {len(registry_data)} entries")
        except Exception as e:
            self.logger.error(f"Error saving server registry: {e}")

    def _compute_config_hash(self, server_name: str) -> str:
        """Compute a hash of the server configuration to track config changes."""
        config = self.get_server_config(server_name)
        if not config:
            return ""

        # Convert config to a stable string representation
        config_str = json.dumps(config, sort_keys=True)
        # Create a hash of the configuration
        return hashlib.md5(config_str.encode()).hexdigest()

    def _is_server_running(self, server_name: str) -> Tuple[bool, Optional[int]]:
        """
        Check if a server is already running by checking its PID.

        Args:
            server_name: Name of the server to check

        Returns:
            Tuple of (is_running, pid) where:
              - is_running: True if the server is running
              - pid: The PID of the running server or None if not running
        """
        # First check if we have a local process
        if server_name in self._local_processes and self._local_processes[server_name].poll() is None:
            return True, self._local_processes[server_name].pid

        # Check if the server is in our registry
        if server_name in self._server_registry:
            server_info = self._server_registry[server_name]
            if server_info.pid:
                # Check if the process is still running
                try:
                    if sys.platform == "win32":
                        # On Windows, use the tasklist command
                        output = subprocess.check_output(['tasklist', '/FI', f'PID eq {server_info.pid}'],
                                                        text=True)
                        return str(server_info.pid) in output, server_info.pid
                    else:
                        # On Unix, use the kill -0 command
                        os.kill(server_info.pid, 0)
                        return True, server_info.pid
                except (ProcessLookupError, OSError, subprocess.SubprocessError):
                    # Process doesn't exist
                    self.logger.info(f"Server {server_name} with PID {server_info.pid} is no longer running")
                    # Remove from registry
                    del self._server_registry[server_name]
                    self._save_server_registry()

        # Server not running
        return False, None

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
        # Log the config for debugging purposes
        self.logger.debug(f"Creating transport for {server_name} with config: {config}")
        # If URL is provided, handle different transport types based on URL and config
        if "url" in config:
            url = config["url"]

            # Handle WebSocket URLs explicitly with configuration
            if url.startswith("ws://") or url.startswith("wss://"):
                # If we have WebSocket specific configuration, use it
                if "ws_config" in config:
                    ws_config = config["ws_config"]
                    self.logger.warning(
                        f"WebSocket configuration options provided but not supported by current WSTransport implementation: {ws_config}"
                    )
                    # Note: Current FastMCP WSTransport doesn't accept configuration parameters,
                    # but we log them to document intent and for future compatibility

                # Create WebSocket transport (currently only accepts URL)
                self.logger.info(f"Creating WSTransport for {server_name} with URL: {url}")
                return WSTransport(url)

            # Handle SSE URLs explicitly if type is specified
            if config.get("type") == "sse":
                self.logger.info(f"Creating SSETransport for {server_name} with type=sse and URL: {url}")
                return SSETransport(url)

            # Handle Streamable HTTP URLs explicitly, identified by paths containing /stream or /mcp/stream
            if ((url.startswith("http://") or url.startswith("https://")) and
                ("/stream" in url or "/mcp/stream" in url)):
                # If we have HTTP-specific configuration, use it
                if "http_config" in config:
                    http_config = config["http_config"]
                    self.logger.info(f"Creating configured StreamableHttpTransport for {server_name} with URL: {url}")

                    # Extract HTTP configuration parameters
                    headers = http_config.get("headers")

                    # Create configured Streamable HTTP transport
                    return StreamableHttpTransport(url, headers=headers)

                # Otherwise, use the default Streamable HTTP transport
                self.logger.info(f"Creating StreamableHttpTransport for {server_name} with URL: {url}")
                return StreamableHttpTransport(url)

            # Let infer_transport handle other URL types
            self.logger.info(f"Using infer_transport for {server_name} with URL: {url}")
            return infer_transport(url)

        # Handle explicit transport types
        transport_type = config.get("type", "").lower()
        # Log transport type for debugging
        self.logger.debug(f"Transport type for {server_name}: '{transport_type}'")

        # Handle WebSocket transport without direct URL
        if transport_type == "websocket":
            # Extract host and port from config
            host = config.get("host", "localhost")
            port = config.get("port", 80)
            path = config.get("path", "/")
            secure = config.get("secure", False)

            # Build WebSocket URL
            protocol = "wss" if secure else "ws"
            url = f"{protocol}://{host}:{port}{path}"

            # Log if we have WebSocket specific configuration (currently not supported)
            if "ws_config" in config:
                ws_config = config["ws_config"]
                self.logger.warning(
                    f"WebSocket configuration options provided but not supported by current WSTransport implementation: {ws_config}"
                )
                # Note: Current FastMCP WSTransport doesn't accept configuration parameters,
                # but we log them to document intent and for future compatibility

            # Create WebSocket transport (currently only accepts URL)
            self.logger.info(f"Creating WSTransport for {server_name} with URL: {url}")
            return WSTransport(url)

        # Handle stdio transport (most common in Claude Desktop)
        if transport_type == "stdio":
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

        # Handle SSE transport
        if transport_type == "sse":
            # For SSE transport, we need a URL
            if "url" not in config:
                raise ValueError(f"SSE transport for {server_name} requires a URL")

            url = config["url"]
            self.logger.info(f"Creating SSETransport for {server_name} with URL: {url}")
            # Note: Explicitly create SSETransport rather than using infer_transport
            # because recent FastMCP versions may infer HTTP URLs as StreamableHttpTransport
            self.logger.debug(f"SSE config: {config}")

            # Force use of SSETransport directly, bypassing infer_transport which
            # tries to use StreamableHttpTransport for URLs ending in /sse in recent FastMCP versions
            return SSETransport(url)

        # Handle Streamable HTTP transport
        if transport_type == "streamable-http" or transport_type == "streamablehttp":
            # For Streamable HTTP transport, we need a URL
            if "url" not in config:
                raise ValueError(f"Streamable HTTP transport for {server_name} requires a URL")

            url = config["url"]

            # Check if we have Streamable HTTP specific configuration
            if "http_config" in config:
                http_config = config["http_config"]
                self.logger.info(f"Creating configured StreamableHttpTransport for {server_name} with URL: {url}")

                # Extract HTTP configuration parameters
                headers = http_config.get("headers")

                # Create configured Streamable HTTP transport
                return StreamableHttpTransport(url, headers=headers)

            # Otherwise, use the default Streamable HTTP transport
            self.logger.info(f"Creating StreamableHttpTransport for {server_name} with URL: {url}")
            return StreamableHttpTransport(url)

        # Fallback
        raise ValueError(f"Unsupported server configuration for {server_name}")
        
    def _is_launchable(self, config: ServerConfig) -> bool:
        """Determine if a server configuration is launchable as a local process."""
        # Only stdio transports with a command can be launched
        return config.get("type") == "stdio" and "command" in config

    def _is_local_stdio_server(self, server_name: str) -> bool:
        """
        Determine if a server is a local STDIO server that relies on stdin/stdout pipes.

        These servers need special handling because they cannot operate as independent
        processes and must be stopped when the client that launched them exits.

        Args:
            server_name: Name of the server to check

        Returns:
            True if this is a local STDIO server, False otherwise
        """
        # Check the configuration first to see if it's a STDIO type
        config = self.get_server_config(server_name)
        if not config or config.get("type") != "stdio":
            return False

        # Check if it has a URL - if it does, it's not a pipe-based STDIO server
        if "url" in config:
            return False

        # If the server is already running in our local processes, it's definitely a local STDIO server
        if server_name in self._local_processes and self._local_processes[server_name].poll() is None:
            return True

        # If we've launched this server previously in this session, consider it a local STDIO server
        if server_name in self._launched_servers:
            return True

        # For servers we haven't launched yet but are configured, we need to look at the configuration
        # Check if it uses a command that depends on stdio for communication (like python or node)
        cmd = config.get("command", "").lower()

        # Most stdio servers that use a command will rely on pipes and should be considered local STDIO servers
        if cmd and self._is_launchable(config):
            # In the future, we might want to refine this to identify socket-based servers
            # that might use stdio type but don't actually rely on pipes for operation
            return True

        return False

    async def query_server(
        self, server_name: str, message: str = None, tool_name: str = "process_message", args: Dict[str, Any] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Send a query to a specific server.

        Args:
            server_name: Name of the server to query
            message: Message to send (optional, depends on tool)
            tool_name: Name of the tool to call (default: process_message)
            args: Additional arguments to pass to the tool (optional)
            **kwargs: Additional keyword arguments to pass directly to the tool

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

                # Add any direct keyword arguments
                for key, value in kwargs.items():
                    tool_args[key] = value

                # Special handling for fetch server
                if server_name == "fetch" and tool_name == "fetch":
                    # For fetch server, url is the main parameter
                    if message is not None:
                        # Check if message is a JSON string
                        if isinstance(message, str) and message.strip().startswith('{'):
                            try:
                                # Try to parse as JSON
                                parsed = json.loads(message)
                                if isinstance(parsed, dict) and "url" in parsed:
                                    # If it has a url key, use the parsed data directly
                                    tool_args.update(parsed)
                                    self.logger.info(f"Using JSON parameters for fetch server with URL: {parsed.get('url')}")
                                else:
                                    # Missing url or not a dict, use as-is
                                    tool_args["url"] = message
                                    self.logger.info(f"Setting URL parameter for fetch server: {message}")
                            except json.JSONDecodeError:
                                # Not valid JSON, use as plain URL
                                tool_args["url"] = message
                                self.logger.info(f"Setting URL parameter for fetch server: {message}")
                        else:
                            # Not JSON, use as plain URL
                            tool_args["url"] = message
                            self.logger.info(f"Setting URL parameter for fetch server: {message}")
                # Special handling for filesystem server
                elif server_name == "filesystem":
                    # Filesystem server needs parameter adaptation based on tool
                    if message is not None:
                        # Check if message is a JSON string
                        if isinstance(message, str) and message.strip().startswith('{'):
                            try:
                                # Try to parse as JSON
                                parsed = json.loads(message)
                                if isinstance(parsed, dict):
                                    # Handle specific tool types for filesystem server
                                    if tool_name == "search_files":
                                        # search_files needs 'path' and 'pattern' parameters
                                        if "directory" in parsed:
                                            # Map 'directory' to 'path' for backward compatibility
                                            parsed["path"] = parsed.pop("directory")
                                        
                                        # Note: The current filesystem server (version 2025.3.28) has a limitation
                                        # where wildcards like "*.txt" don't work properly in search patterns.
                                        # Only exact filenames work reliably.
                                        if "pattern" not in parsed:
                                            # Set default pattern if not provided - use exact filename if known
                                            if "filename" in parsed:
                                                parsed["pattern"] = parsed.pop("filename")
                                            else:
                                                parsed["pattern"] = "*"
                                                self.logger.warning(
                                                    "Note: search_files with wildcard patterns like '*' or '*.txt' may not "
                                                    "work with the current filesystem server version. For reliable results, "
                                                    "provide an exact filename instead."
                                                )
                                        elif "*" in parsed["pattern"] or "?" in parsed["pattern"]:
                                            self.logger.warning(
                                                f"Note: search_files with wildcard pattern '{parsed['pattern']}' may not "
                                                f"work with the current filesystem server version. For reliable results, "
                                                f"provide an exact filename instead."
                                            )
                                            
                                        self.logger.info(f"Mapping filesystem search_files parameters: path={parsed.get('path')}, pattern={parsed.get('pattern')}")
                                    
                                    elif tool_name == "list_directory":
                                        # list_directory needs 'path' parameter
                                        if "directory" in parsed:
                                            # Map 'directory' to 'path' for backward compatibility
                                            parsed["path"] = parsed.pop("directory")
                                        self.logger.info(f"Mapping filesystem list_directory parameter: path={parsed.get('path')}")
                                    
                                    elif tool_name in ["read_file", "write_file", "get_file_info"]:
                                        # These tools require a 'path' parameter
                                        self.logger.info(f"Using filesystem parameters for {tool_name}: {parsed}")
                                    
                                    # Update tool args with parsed parameters
                                    tool_args.update(parsed)
                                else:
                                    # Not a dict, use as message parameter
                                    tool_args["message"] = message
                            except json.JSONDecodeError:
                                # Not valid JSON, use as regular message
                                tool_args["message"] = message
                        else:
                            # Not JSON, might be a direct path
                            if tool_name in ["read_file", "write_file", "get_file_info", "list_directory", "search_files"]:
                                tool_args["path"] = message
                            else:
                                tool_args["message"] = message
                # Handle JSON string in message parameter
                elif message is not None and not tool_args:
                    # Try to parse message as JSON if it's a string
                    if isinstance(message, str):
                        try:
                            parsed = json.loads(message)
                            if isinstance(parsed, dict):
                                # Use parsed JSON as tool arguments
                                tool_args.update(parsed)
                                self.logger.debug(f"Parsed JSON arguments from message: {tool_args}")
                            else:
                                # Not a dict, use as message parameter
                                tool_args["message"] = message
                        except json.JSONDecodeError:
                            # Not JSON, use as regular message
                            tool_args["message"] = message
                    else:
                        # Not a string, use as regular message
                        tool_args["message"] = message
                # Regular handling for message parameter when other args exist
                elif message is not None:
                    # Only set message parameter if not already in tool_args
                    if "message" not in tool_args:
                        tool_args["message"] = message

                # Call the tool with the combined arguments
                self.logger.debug(f"Calling tool {tool_name} with args: {tool_args}")
                try:
                    response = await client.call_tool(tool_name, tool_args)
                    return response
                except Exception as e:
                    detailed_error = None
                    # Extract the actual error message from TaskGroup exceptions
                    if "unhandled errors in a TaskGroup" in str(e):
                        import traceback
                        tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
                        error_found = False
                        
                        # First try to find a ClientError in the traceback
                        for line in reversed(tb_lines):
                            if "Error:" in line and "ClientError:" in line:
                                error_msg = line.split("ClientError:", 1)[1].strip()
                                self.logger.error(f"Server error: {error_msg}")
                                detailed_error = error_msg
                                error_found = True
                                break
                        
                        # If no ClientError found, look for specific error patterns
                        if not error_found:
                            # Look for filesystem server errors
                            for line in tb_lines:
                                if "path outside allowed directories:" in line:
                                    matched_part = line.split("path outside allowed directories:", 1)[1].strip()
                                    error_msg = f"Access denied - path outside allowed directories: {matched_part}"
                                    self.logger.error(f"Filesystem error: {error_msg}")
                                    detailed_error = error_msg
                                    error_found = True
                                    break
                                elif "ENOENT:" in line:
                                    matched_part = line.split("ENOENT:", 1)[1].strip()
                                    error_msg = f"ENOENT: {matched_part}"
                                    self.logger.error(f"Filesystem error: {error_msg}")
                                    detailed_error = error_msg
                                    error_found = True
                                    break
                                elif "EACCES:" in line:
                                    matched_part = line.split("EACCES:", 1)[1].strip()
                                    error_msg = f"EACCES: {matched_part}"
                                    self.logger.error(f"Filesystem error: {error_msg}")
                                    detailed_error = error_msg
                                    error_found = True
                                    break
                        
                        # If no filesystem-specific error found, look for any error message
                        if not error_found:
                            for line in reversed(tb_lines):
                                if "Error:" in line:
                                    error_parts = line.split("Error:", 1)
                                    if len(error_parts) > 1:
                                        error_msg = error_parts[1].strip()
                                        self.logger.error(f"Error details: {error_msg}")
                                        detailed_error = error_msg
                                        error_found = True
                                        break
                        
                        # If still no detailed error found, check exception cause and context
                        if not error_found:
                            if hasattr(e, "__cause__") and e.__cause__ is not None:
                                self.logger.error(f"Underlying cause: {e.__cause__}")
                            if hasattr(e, "__context__") and e.__context__ is not None:
                                self.logger.error(f"Error context: {e.__context__}")
                                
                    # Log the full error
                    self.logger.debug(f"Full error: {str(e)}")
                    
                    # Raise a more specific error if we found details
                    if detailed_error:
                        raise RuntimeError(detailed_error) from e
                    else:
                        raise
        except Exception as e:
            self.logger.error(f"Error querying server {server_name}: {e}")
            return None

    def get_server_logs(self, server_name: str) -> Dict[str, Optional[str]]:
        """Get the paths to the log files for a server.
        
        Args:
            server_name: Name of the server to get logs for
            
        Returns:
            Dictionary with 'stdout' and 'stderr' keys pointing to log file paths,
            or None if no logs are available
        """
        # Initialize result with None values
        result = {'stdout': None, 'stderr': None}
        
        # First check if we have a local process with log file references
        if server_name in self._local_processes:
            process = self._local_processes[server_name]
            if hasattr(process, '_stdout_path'):
                result['stdout'] = str(process._stdout_path)
            if hasattr(process, '_stderr_path'):
                result['stderr'] = str(process._stderr_path)
        
        # If no logs found from local process, check the server registry
        if result['stdout'] is None and result['stderr'] is None:
            if server_name in self._server_registry:
                server_info = self._server_registry[server_name]
                if server_info.stdout_log:
                    result['stdout'] = str(server_info.stdout_log)
                if server_info.stderr_log:
                    result['stderr'] = str(server_info.stderr_log)
        
        # If no logs found in registry, try to find the most recent logs for this server
        if result['stdout'] is None and result['stderr'] is None:
            try:
                # Look for any log files for this server
                stdout_logs = list(self.LOG_DIR.glob(f"{server_name}_*_stdout.log"))
                stderr_logs = list(self.LOG_DIR.glob(f"{server_name}_*_stderr.log"))
                
                # Sort by modification time, most recent first
                stdout_logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                stderr_logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                
                if stdout_logs:
                    result['stdout'] = str(stdout_logs[0])
                if stderr_logs:
                    result['stderr'] = str(stderr_logs[0])
            except Exception as e:
                self.logger.error(f"Error finding log files for {server_name}: {e}")
        
        return result
        
    async def launch_server_with_errors(self, server_name: str) -> tuple[bool, Optional[str]]:
        """Launch a local server process and return detailed error information if it fails.

        Args:
            server_name: Name of the server to launch

        Returns:
            Tuple of (success, error_details) where:
              - success: True if server was successfully launched
              - error_details: String with error details if launch failed, None otherwise
        """
        config = self.get_server_config(server_name)
        if not config:
            return False, "No configuration found for server"

        if not self._is_launchable(config):
            return False, f"Server {server_name} is not launchable (not a stdio server)"

        # Check if the server is already running
        is_running, pid = self._is_server_running(server_name)
        if is_running:
            self.logger.info(f"Server {server_name} is already running with PID {pid}")
            # Make sure it's in our launched servers set
            self._launched_servers.add(server_name)
            return True, None

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
                    error_msg = (
                        "Port 3001 is already in use. The Playwright server requires port 3001 to be available. "
                        "Please stop any other services using this port before launching the Playwright server."
                    )
                    self.logger.error(error_msg)
                    return False, error_msg
            except Exception as e:
                self.logger.warning(f"Failed to check port status: {e}")

        try:
            # Construct full command
            full_cmd = [cmd] + args
            self.logger.info(f"Launching server {server_name}: {' '.join(full_cmd)}")

            # Log directory is already created in __init__

            # Create log files for stdout and stderr
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            stdout_log = self.LOG_DIR / f"{server_name}_{timestamp}_stdout.log"
            stderr_log = self.LOG_DIR / f"{server_name}_{timestamp}_stderr.log"

            # Open log files
            stdout_file = open(stdout_log, "w")
            stderr_file = open(stderr_log, "w")

            # Log the location of the output files
            self.logger.info(f"Server {server_name} stdout log: {stdout_log}")
            self.logger.info(f"Server {server_name} stderr log: {stderr_log}")

            # Launch process with different configurations depending on platform
            if sys.platform == "win32":
                # On Windows, CREATE_NEW_PROCESS_GROUP flag is needed
                process = subprocess.Popen(
                    full_cmd,
                    stdin=subprocess.PIPE,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    env=env,
                    text=True,
                    bufsize=0,  # Unbuffered
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            elif sys.platform == "darwin":
                # On macOS, use nohup to ensure persistence and start_new_session
                # to create a new process group - this provides belt-and-suspenders approach
                full_nohup_cmd = ["nohup"] + full_cmd
                process = subprocess.Popen(
                    full_nohup_cmd,
                    stdin=subprocess.PIPE,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    env=env,
                    text=True,
                    bufsize=0,  # Unbuffered
                    start_new_session=True,  # Detach from parent process
                    preexec_fn=os.setpgrp  # Create new process group
                )
            else:
                # On other Unix platforms, start_new_session creates a new process group
                # This allows the process to continue running after the parent exits
                process = subprocess.Popen(
                    full_cmd,
                    stdin=subprocess.PIPE,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    env=env,
                    text=True,
                    bufsize=0,  # Unbuffered
                    start_new_session=True,  # Detach from parent process
                    preexec_fn=os.setpgrp  # Create new process group
                )

            # Store the process
            self._local_processes[server_name] = process

            # Give it a moment to start up
            await asyncio.sleep(1)

            # Check if the process is still running or if it exited with code 0
            if process.poll() is not None and process.returncode != 0:
                # Read the last few lines from the stderr log file for error reporting
                try:
                    # First flush and close the files to ensure data is written
                    stderr_file.flush()
                    stderr_file.close()
                    stdout_file.close()

                    # Read the last 10 lines of the stderr log
                    with open(stderr_log, 'r') as f:
                        stderr_lines = f.readlines()
                        last_lines = stderr_lines[-10:] if len(stderr_lines) > 10 else stderr_lines
                        stderr_content = ''.join(last_lines)
                except Exception as e:
                    stderr_content = f"Could not read error output: {e}"

                error_msg = f"Server {server_name} failed to start. Exit code: {process.returncode}\nError: {stderr_content}"
                self.logger.error(error_msg)
                self.logger.error(f"For full error details, see log file: {stderr_log}")
                return False, stderr_content
            elif process.poll() is not None and process.returncode == 0:
                # Exit code 0 indicates the server might have detached successfully
                self.logger.info(f"Server {server_name} appears to have detached with exit code 0, which usually indicates success")

            # We need to maintain references to the log files we opened
            # Store them with the process for later cleanup
            process._stdout_file = stdout_file
            process._stderr_file = stderr_file
            process._stdout_path = stdout_log
            process._stderr_path = stderr_log

            # Add to our tracking set of launched servers
            self._launched_servers.add(server_name)

            # Create a server info object and add to registry
            config_hash = self._compute_config_hash(server_name)
            server_info = ServerInfo(
                server_name=server_name,
                pid=process.pid,
                start_time=time.time(),
                config_hash=config_hash,
                log_dir=self.LOG_DIR,
                stdout_log=stdout_log,
                stderr_log=stderr_log
            )
            self._server_registry[server_name] = server_info
            self._save_server_registry()

            self.logger.info(f"Successfully launched server {server_name} with PID {process.pid}")
            self.logger.info(f"Server {server_name} logs can be found at:")
            self.logger.info(f"  stdout: {stdout_log}")
            self.logger.info(f"  stderr: {stderr_log}")
            return True, None
        except Exception as e:
            error_msg = f"Error launching server {server_name}: {e}"
            self.logger.error(error_msg)

            # Close file handles if they were opened
            try:
                if 'stdout_file' in locals() and stdout_file:
                    stdout_file.close()
                if 'stderr_file' in locals() and stderr_file:
                    stderr_file.close()
            except Exception as file_err:
                self.logger.error(f"Error closing log files: {file_err}")

            # Clean up tracking
            if server_name in self._local_processes:
                self._local_processes.pop(server_name)
            if server_name in self._launched_servers:
                self._launched_servers.remove(server_name)

            return False, str(e)

    async def launch_server(self, server_name: str) -> bool:
        """Launch a local server process based on configuration.

        Args:
            server_name: Name of the server to launch

        Returns:
            True if server was successfully launched, False otherwise
        """
        config = self.get_server_config(server_name)
        if not config:
            error_msg = f"No configuration found for server: {server_name}"
            self.logger.error(error_msg)
            return False

        if not self._is_launchable(config):
            error_msg = f"Server {server_name} is not launchable (not a stdio server)"
            self.logger.error(error_msg)
            return False

        # From here, we'll use the implementation from launch_server_with_errors
        # but just return the success status
        success, error_details = await self.launch_server_with_errors(server_name)
        
        # Log error details for debugging
        if not success and error_details:
            self.logger.error(f"Failed to launch server {server_name}. Error: {error_details}")
            
        return success
            
    async def stop_server(self, server_name: str) -> bool:
        """Stop a running local server process.

        Args:
            server_name: Name of the server to stop

        Returns:
            True if server was successfully stopped, False otherwise
        """
        # First check if we have a record of this server in our local processes
        if server_name in self._local_processes:
            process = self._local_processes[server_name]
            if process.poll() is not None:
                # Process already stopped
                self._local_processes.pop(server_name)
                # Remove from registry
                if server_name in self._server_registry:
                    del self._server_registry[server_name]
                    self._save_server_registry()
                return True
        else:
            # Check if it's in the server registry
            is_running, pid = self._is_server_running(server_name)
            if not is_running:
                self.logger.warning(f"Server {server_name} is not running")
                # Clean up registry if needed
                if server_name in self._server_registry:
                    del self._server_registry[server_name]
                    self._save_server_registry()
                return False

            # Server is running but not in our local processes, try to stop it by PID
            process = None
            try:
                # Try to get the pid from the registry
                if server_name in self._server_registry and self._server_registry[server_name].pid:
                    pid = self._server_registry[server_name].pid
                    self.logger.info(f"Attempting to stop server {server_name} with PID {pid}")

                    # On Windows, use taskkill
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                                    check=False, capture_output=True)
                    else:
                        # On Unix, use kill
                        os.kill(pid, signal.SIGTERM)

                    # Wait a moment to see if it terminates
                    await asyncio.sleep(0.5)

                    # Check if still running
                    try:
                        os.kill(pid, 0)
                        # Still running, try SIGKILL
                        if sys.platform != "win32":
                            os.kill(pid, signal.SIGKILL)
                    except OSError:
                        # Process not found, which means it terminated
                        pass

                    # Remove from registry
                    del self._server_registry[server_name]
                    self._save_server_registry()
                    self.logger.info(f"Stopped server {server_name} with PID {pid}")
                    return True
                else:
                    self.logger.warning(f"No PID found for server {server_name}")
                    return False
            except Exception as e:
                self.logger.error(f"Error stopping server {server_name} by PID: {e}")
                return False
            
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
                
            # Clean up file handles if they exist
            try:
                if hasattr(process, '_stdout_file'):
                    process._stdout_file.flush()
                    process._stdout_file.close()
                    self.logger.info(f"Closed stdout log file for {server_name}")

                if hasattr(process, '_stderr_file'):
                    process._stderr_file.flush()
                    process._stderr_file.close()
                    self.logger.info(f"Closed stderr log file for {server_name}")

                if hasattr(process, '_stdout_path') and hasattr(process, '_stderr_path'):
                    self.logger.info(f"Server {server_name} logs are available at:")
                    self.logger.info(f"  stdout: {process._stdout_path}")
                    self.logger.info(f"  stderr: {process._stderr_path}")
            except Exception as e:
                self.logger.warning(f"Error closing log files for {server_name}: {e}")

            # Clean up tracking
            self._local_processes.pop(server_name)
            if server_name in self._launched_servers:
                self._launched_servers.remove(server_name)

            # Remove from registry
            if server_name in self._server_registry:
                del self._server_registry[server_name]
                self._save_server_registry()

            self.logger.info(f"Server {server_name} stopped successfully")
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

    async def close(self, stop_servers: bool = True) -> None:
        """
        Close all client connections and optionally stop local STDIO servers.

        This method respects the server type when determining what to stop:
        - Local STDIO servers (relying on stdin/stdout pipes) are stopped only if stop_servers=True
        - Socket-based servers remain running regardless of the stop_servers parameter
        - Remote servers are never stopped, only disconnected

        Args:
            stop_servers: If True (default), stop local STDIO servers that rely on pipes.
                         If False, only close client connections but leave all server processes running.
        """
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

        # Then stop local STDIO server processes if requested
        if stop_servers:
            await self.stop_local_stdio_servers()

    async def stop_local_stdio_servers(self) -> Dict[str, bool]:
        """
        Stop only local STDIO servers that rely on stdin/stdout pipes.

        This is used for the default close() behavior, which only stops
        servers that rely on direct pipe communication and would become orphaned
        when the parent process exits. Socket-based and remote servers are not affected.

        This selective approach ensures that:
        1. Pipe-based servers are properly cleaned up to avoid orphaned processes
        2. Socket-based servers can remain running for future client connections
        3. Remote servers are never affected

        Returns:
            Dictionary mapping server names to stop success status
        """
        results = {}

        # Check which servers in our local processes are STDIO servers
        local_servers = list(self._local_processes.keys())
        for server_name in local_servers:
            if self._is_local_stdio_server(server_name):
                self.logger.info(f"Stopping local STDIO server: {server_name}")
                results[server_name] = await self.stop_server(server_name)
            else:
                self.logger.info(f"Not stopping non-STDIO server: {server_name}")

        # Log summary
        success_count = sum(1 for success in results.values() if success)
        if results:
            self.logger.info(f"Stopped {success_count} of {len(results)} local STDIO servers")
        else:
            self.logger.info("No local STDIO servers to stop")

        return results

    async def stop_all_servers(self) -> Dict[str, bool]:
        """
        Stop all running servers tracked by this client.

        Returns:
            Dictionary mapping server names to stop success status
        """
        results = {}

        # First, stop servers in our local processes
        local_servers = list(self._local_processes.keys())
        for server_name in local_servers:
            results[server_name] = await self.stop_server(server_name)

        # Then, check the registry for any servers not in our local processes
        for server_name, server_info in list(self._server_registry.items()):
            if server_name not in results:
                results[server_name] = await self.stop_server(server_name)

        # Log summary
        success_count = sum(1 for success in results.values() if success)
        if results:
            self.logger.info(f"Stopped {success_count} of {len(results)} servers")
        else:
            self.logger.info("No servers to stop")

        return results

    async def __aenter__(self):
        """Context manager support."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure all connections are closed when exiting context."""
        # Only stop local STDIO servers when exiting context
        await self.close(stop_servers=True)