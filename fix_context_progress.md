# Fix for Missing Context.progress() Method in MCP

## Issue Description

When connecting to the Crunchbase MCP server, we're encountering the following error when trying to use any of the tools:

```
Error executing tool X: 'Context' object has no attribute 'progress'
```

This error occurs because the Crunchbase MCP server code is using the `ctx.progress()` method, but the FastMCP Context object provided by the framework doesn't have this attribute.

## Recommended Fix for the Crunchbase Server

To fix this issue in the Crunchbase server, you should modify the server code to handle the missing `progress` method gracefully. Here's a simple patch that you can apply:

### Option 1: Add a Monkey Patch to the Server Startup

Add this code near the beginning of your server setup, before any tool definitions:

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

### Option 2: Add Helper Function for Tool Implementations

Alternatively, if you prefer not to modify the Context class directly, you can create a helper function to use in your tool implementations:

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

Then update your tool implementations to use this helper function:

```python
async def import_browser_cookies(cookie_file: str, ctx: Context) -> Dict[str, Any]:
    # Use the helper function instead of ctx.progress directly
    await report_progress(ctx, f"Importing cookies from {cookie_file}")
    # Rest of the implementation...
```

### Option 3: Modify Each Tool Implementation

If you have only a few tools, you could update each one with a try/except block:

```python
async def import_browser_cookies(cookie_file: str, ctx: Context) -> Dict[str, Any]:
    try:
        await ctx.progress(f"Importing cookies from {cookie_file}")
    except AttributeError:
        # Context doesn't have progress method, continue anyway
        pass
    
    # Rest of the implementation...
```

## Additional Considerations

1. **Backward Compatibility**: Adding the progress method ensures compatibility with older MCP client implementations.

2. **Future Proofing**: Consider checking for other Context methods that might be used in your code but may not be available in all client implementations.

3. **Proper Error Handling**: Ensure all tool implementations have proper error handling to gracefully handle exceptions.

4. **Context Documentation**: Create documentation for your server that explains any custom Context methods or requirements.

## Technical Background

FastMCP defines the Context class in its codebase, but implementations can vary. The Context provided by the framework is a basic implementation with methods like `info()`, `warning()`, and `error()`, but not all implementations include a `progress()` method.

By making this change, your server will be compatible with a wider range of MCP clients while maintaining the functionality you need.