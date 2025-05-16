# Recommendations for Crunchbase MCP Server Integration

## Issue Summary

When integrating with the Crunchbase MCP server, we've identified an incompatibility issue with the multi-server client. The server code relies on a `ctx.progress()` method that isn't available in the standard FastMCP Context implementation. This causes all tool calls to fail with the error:

```
Error executing tool X: 'Context' object has no attribute 'progress'
```

## Investigation Process

1. **Initial Connection Testing**:
   - Successfully connected to the server and listed available tools
   - Confirmed the server was running and processing requests
   - Identified the error in the tool implementation

2. **Transport Comparison**:
   - Tested with both STDIO and HTTP transports
   - Both transport types exhibited the same error
   - Confirmed it was a server-side issue, not a client or transport issue

3. **Error Analysis**:
   - Examined the server logs to verify requests were being processed
   - Identified the root cause as missing `ctx.progress()` method
   - Developed multiple solutions based on the severity of the issue

## Recommendations

### 1. Server-Side Fixes (Preferred)

The most robust solution is to update the server code to handle the missing `progress` method gracefully:

#### Option A: Monkey Patch at Startup

Add this code early in the server initialization:

```python
# Monkey patch Context to add progress method if missing
from fastmcp import Context
if not hasattr(Context, 'progress'):
    async def progress_noop(self, message, *args, **kwargs):
        """No-op progress method for backward compatibility."""
        # Optionally log the message for debugging
        import logging
        logging.getLogger('crunchbase_mcp').debug(f"Progress: {message}")
    
    # Add the method to the Context class
    setattr(Context, 'progress', progress_noop)
```

#### Option B: Helper Function Approach

Add a helper function and use it instead of direct `ctx.progress()` calls:

```python
async def report_progress(ctx, message, *args, **kwargs):
    """Safe progress reporting that works with any Context implementation."""
    if hasattr(ctx, 'progress'):
        await ctx.progress(message, *args, **kwargs)
    else:
        # Optionally log the message for debugging
        import logging
        logging.getLogger('crunchbase_mcp').debug(f"Progress: {message}")
```

#### Option C: Inline Try/Except

For a quick fix, wrap each `ctx.progress()` call in a try/except block:

```python
try:
    await ctx.progress("Working on task...")
except AttributeError:
    # Context doesn't have progress method, continue anyway
    pass
```

### 2. Client-Side Workarounds (Temporary)

If modifying the server isn't feasible, consider these client-side workarounds:

#### Option A: Proxy Server

Create a proxy server that intercepts requests, adds the missing `progress` method, and forwards them to the Crunchbase server. We've created a starter implementation in `mcp_context_patch.py`.

#### Option B: Custom Transport

Implement a custom transport that enhances the Context object before passing it to tools. This is more complex but could be done by subclassing StreamableHttpTransport.

## Implementation Assistance

We've provided two helper files to assist with implementing these solutions:

1. **`fix_context_progress.md`**: Detailed technical explanation of the issue and fix options.
2. **`apply_context_progress_patch.py`**: Script to automatically apply the patch to the server code.

To use the patch script:

```bash
# Dry run to see what would be changed
python apply_context_progress_patch.py --server-dir /path/to/mcp-server-crunchbase --dry-run

# Apply the monkey patch
python apply_context_progress_patch.py --server-dir /path/to/mcp-server-crunchbase --patch-type monkey

# Alternative: Apply helper function approach
python apply_context_progress_patch.py --server-dir /path/to/mcp-server-crunchbase --patch-type helper

# Alternative: Apply inline try/except blocks
python apply_context_progress_patch.py --server-dir /path/to/mcp-server-crunchbase --patch-type inline
```

## Conclusion

The issue is relatively simple to fix but prevents any usage of the Crunchbase server tools through the multi-server client. By implementing one of the recommended fixes, the server will be compatible with a wider range of MCP clients while maintaining the progress reporting functionality for clients that support it.

We recommend the monkey patch approach as it's the simplest and most comprehensive solution, requiring changes to only one file while fixing all tool implementations at once.