#!/usr/bin/env python
"""
Script to run the test suite for MCP Multi-Server Client.

Usage:
    python run_tests.py [options]

Options:
    -v, --verbose    : Increase verbosity of output
    -x, --exit-first : Exit after first test failure
    --npx-only       : Run only npx server tests
    --python-only    : Run only Python server tests
"""

import sys
import pytest


def main():
    """Run the test suite."""
    args = sys.argv[1:]

    # Build pytest arguments
    pytest_args = [
        "tests/test_servers.py",
        "tests/test_npx_servers.py",
        "tests/test_transports.py",
        "tests/test_fetch_server.py",
        "tests/test_additional_servers.py"
    ]

    # Handle verbose flag
    if "-v" in args or "--verbose" in args:
        pytest_args.append("-v")
        if "-v" in args:
            args.remove("-v")
        if "--verbose" in args:
            args.remove("--verbose")

    # Handle exit first flag
    if "-x" in args or "--exit-first" in args:
        pytest_args.append("-x")
        if "-x" in args:
            args.remove("-x")
        if "--exit-first" in args:
            args.remove("--exit-first")

    # Handle server type filtering
    if "--npx-only" in args:
        # Use the dedicated NPX tests file instead of keyword filtering
        pytest_args = ["tests/test_npx_servers.py"]
        args.remove("--npx-only")

    if "--python-only" in args:
        # Only include test_servers.py and filter for Python
        pytest_args = ["tests/test_servers.py"]
        pytest_args.append("-k")
        pytest_args.append("python")
        args.remove("--python-only")

    # Add any remaining arguments
    pytest_args.extend(args)

    # Run the tests
    print(f"Running tests with arguments: {pytest_args}")
    exit_code = pytest.main(pytest_args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()