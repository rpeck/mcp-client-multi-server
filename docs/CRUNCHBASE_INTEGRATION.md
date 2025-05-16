# Crunchbase Integration Guide

This guide explains how to connect the MCP Multi-Server Client to the Crunchbase MCP Server for company data retrieval.

## Prerequisites

1. A running Crunchbase MCP Server (from mcp-server-crunchbase project)
2. Valid Crunchbase authentication cookies
3. MCP Multi-Server Client properly configured

## Quick Setup

### 1. Configure the Client

Add the Crunchbase server to your `config.json`:

```json
{
  "mcpServers": {
    "crunchbase": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp/stream",
      "http_config": {
        "headers": {
          "X-Debug": "true",
          "X-Client": "multi-server-client"
        },
        "timeout": 180.0
      }
    }
  }
}
```

### 2. Server Authentication Process

Before connecting, make sure:

1. The Crunchbase server has valid authentication cookies 
2. Use the **Easy Login Tool** from the mcp-server-crunchbase project:
   ```bash
   # Navigate to the mcp-server-crunchbase directory
   cd /path/to/mcp-server-crunchbase
   
   # Run the Easy Login tool
   python easy_login.py
   ```
3. Follow the browser-based login process to generate `.cb_session.json`

### 3. Start the Server

```bash
# Navigate to the mcp-server-crunchbase directory
cd /path/to/mcp-server-crunchbase

# Start the server
./server.sh start
```

### 4. Search for Companies

Use the included `crunchbase_search.py` utility:

```bash
# Check authentication status
python crunchbase_search.py check

# Search for a company by name
python crunchbase_search.py company "Anthropic"

# Get a company by slug
python crunchbase_search.py slug "anthropic"
```

## Advanced Configuration and Troubleshooting

### Connection Issues

If you encounter connection issues:

1. Verify the server is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check server logs for errors:
   ```bash
   cd /path/to/mcp-server-crunchbase
   ./server.sh logs
   ```

3. Verify authentication cookie status:
   ```bash
   cd /path/to/mcp-server-crunchbase
   python cookie_manager.py --validate
   ```

### Cookie Management

The Crunchbase MCP Server relies on valid authentication cookies:

1. **Cookie Expiration**: Crunchbase cookies expire regularly. If searches start failing:
   ```bash
   # Update cookies with Easy Login
   cd /path/to/mcp-server-crunchbase
   python easy_login.py
   ```

2. **Cookie Validation**:
   ```bash
   cd /path/to/mcp-server-crunchbase
   python cookie_manager.py --validate
   ```

3. **Manual Cookie Import** (if necessary):
   ```bash
   python crunchbase_search.py import /path/to/cookies.json
   ```

### Available Tools

The Crunchbase MCP Server provides these tools:

1. `search_company_name`: Search for companies by name
   ```bash
   python -m mcp_client_multi_server -c config.json query --server crunchbase --tool search_company_name --message '{"query": "Anthropic"}'
   ```

2. `get_company_by_slug`: Get detailed information about a company by its URL slug
   ```bash
   python -m mcp_client_multi_server -c config.json query --server crunchbase --tool get_company_by_slug --message '{"slug": "anthropic"}'
   ```

3. `check_auth_status`: Verify authentication status
   ```bash
   python -m mcp_client_multi_server -c config.json query --server crunchbase --tool check_auth_status
   ```

4. `import_browser_cookies`: Import cookies from a file
   ```bash
   python -m mcp_client_multi_server -c config.json query --server crunchbase --tool import_browser_cookies --message '{"cookie_file": "/path/to/cookies.json"}'
   ```

## Using with Python Code

```python
import asyncio
from mcp_client_multi_server import MultiServerClient

async def search_crunchbase():
    client = MultiServerClient(config_path="config.json")
    
    try:
        async with client:
            # Check authentication
            auth_result = await client.query_server(
                server_name="crunchbase",
                tool_name="check_auth_status"
            )
            print(f"Authentication status: {auth_result}")
            
            # Search for a company
            result = await client.query_server(
                server_name="crunchbase",
                tool_name="search_company_name",
                args={"query": "Anthropic"}
            )
            
            # Process the result
            if hasattr(result, "text"):
                print(result.text)
            elif isinstance(result, list) and hasattr(result[0], "text"):
                print(result[0].text)
            else:
                print(result)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(search_crunchbase())
```

## Known Issues and Limitations

### Trial Account Limitations

If using a Crunchbase Pro Trial account:
- Search functionality may be limited
- You may be redirected to upgrade pages
- Use direct slug lookup for more reliable results

### Context Progress Method

If you see errors related to `Context` object having no attribute `progress`:

1. This is a compatibility issue between the server and client
2. Apply the patch from the server-side repository:
   ```bash
   cd /path/to/mcp-server-crunchbase
   python apply_context_progress_patch.py
   ```
3. See `CRUNCHBASE_SERVER_RECOMMENDATIONS.md` for detailed information

## Further Resources

- [Crunchbase MCP Server Documentation](../../../mcp-server-crunchbase/README.md)
- [Easy Login Instructions](../../../mcp-server-crunchbase/EASY_LOGIN_INSTRUCTIONS.md)
- [Cookie Handling Guide](../../../mcp-server-crunchbase/COOKIE_HANDLING.md)
- [MCP Client Multi-Server Documentation](../README.md)