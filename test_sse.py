#!/usr/bin/env python3
"""Test script to manually check SSE server connectivity."""

import aiohttp
import asyncio

async def test_sse_connection():
    """Connect to SSE endpoint and print status and response."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:9001/mcp/sse') as resp:
                print(f'Status: {resp.status}')
                print(f'Headers: {resp.headers}')
                text = await resp.text()
                print(f'Response text: {text[:200]}...' if len(text) > 200 else text)
    except Exception as e:
        print(f"Error connecting to SSE server: {e}")

if __name__ == "__main__":
    asyncio.run(test_sse_connection())