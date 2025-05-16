# Migrating from Custom progress() to Standard report_progress()

## Background

We've identified that the crunchbase server is using a custom `ctx.progress()` method that is not part of the standard FastMCP implementation. The standard method in FastMCP for reporting progress is `ctx.report_progress()`.

## The Standard Method

The standard FastMCP implementation includes `report_progress()` with the following signature:

```python
async def report_progress(
    self, 
    progress: float, 
    total: float | None = None, 
    message: str | None = None
) -> None:
```

This method is designed to report progress for long-running operations with:
- `progress`: A float value indicating current progress
- `total`: An optional float for the total expected work
- `message`: An optional string message describing the current state

## Migration Strategy

We've created a script to automatically migrate custom `progress()` calls to the standard `report_progress()` method. The script will:

1. Scan all Python files in the crunchbase server directory
2. Identify calls to `ctx.progress()`
3. Replace them with equivalent `ctx.report_progress()` calls
4. Create backups of all modified files

### Options for Migration

There are two main approaches:

#### 1. Direct Replacement (Cleaner)

Replace all `ctx.progress(message)` calls with `ctx.report_progress(progress=0.5, message=message)`.

**Pros**:
- Follows the standard API
- Cleaner code that uses the official interface

**Cons**:
- May break compatibility if other code expects `progress()` to exist

#### 2. Compatibility Layer (Safer)

Add a compatibility layer that implements `progress()` using `report_progress()`, while also updating direct calls.

**Pros**:
- Maintains backward compatibility
- Provides a transition path

**Cons**:
- Keeps deprecated method around
- Slightly messier codebase

## Usage Instructions

To migrate from `progress()` to `report_progress()`, run the provided script:

```bash
# First, run in dry-run mode to see what would change
python report_progress_migration.py --server-dir /path/to/mcp-server-crunchbase --dry-run

# When ready, run the actual migration
python report_progress_migration.py --server-dir /path/to/mcp-server-crunchbase

# For a safer migration with backward compatibility
python report_progress_migration.py --server-dir /path/to/mcp-server-crunchbase --backwards-compatible
```

## Example Transformations

Here are examples of how the migration transforms code:

### Simple Message Only

**Before**:
```python
await ctx.progress("Loading data...")
```

**After**:
```python
await ctx.report_progress(progress=0.5, message="Loading data...")
```

### With Progress Value

**Before**:
```python
await ctx.progress("Processing items...", progress=0.75)
```

**After**:
```python
await ctx.report_progress(progress=0.75, message="Processing items...")
```

### With Multiple Parameters

**Before**:
```python
await ctx.progress("Analyzing results...", progress=0.9, total=1.0, custom_param="value")
```

**After**:
```python
await ctx.report_progress(progress=0.9, message="Analyzing results...", total=1.0)
```
(Note: Custom parameters not used by report_progress are removed)

## Verification

After migration, you should test the server to ensure:

1. All progress reporting functions correctly
2. The server interfaces properly with different MCP clients
3. No regressions are introduced

## Conclusion

By migrating to the standard `report_progress()` method, the crunchbase server will be more compatible with the broader MCP ecosystem and will follow official FastMCP conventions.