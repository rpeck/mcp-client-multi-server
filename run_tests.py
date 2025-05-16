#!/usr/bin/env python
"""
Script to run the test suite for MCP Multi-Server Client.

Usage:
    python run_tests.py [options]

Options:
    -v, --verbose     : Increase verbosity of output
    -x, --exit-first  : Exit after first test failure
    --npx-only        : Run only npx server tests
    --python-only     : Run only Python server tests
    --cleanup-only    : Run only server cleanup and error handling tests
    --filesystem-only : Run only filesystem server tests
    --transport-only  : Run only transport tests (STDIO, SSE, HTTP)
    --all             : Run all tests including slow or unreliable ones
    --skip-slow       : Skip slow tests that might be unreliable in CI
    --cli-only        : Run only CLI and shell script tests
    --shell-only      : Run only shell script tests
"""

import sys
import pytest


def main():
    """Run the test suite."""
    args = sys.argv[1:]
    shell_test_flag = False

    # Define test categories
    core_tests = [
        "tests/test_servers.py",
        "tests/test_transports.py",
    ]

    npx_tests = [
        "tests/test_npx_servers.py",
        "tests/test_playwright_port_handling.py"
    ]

    additional_tests = [
        "tests/test_fetch_server.py",
        "tests/test_additional_servers.py",
        "tests/test_uvx_transport.py",
    ]

    filesystem_tests = [
        "tests/test_filesystem_server.py",
    ]
    
    transport_tests = [
        "tests/test_echo_transports.py",
        "tests/test_transports.py",
        "tests/test_all_transports.py",
    ]

    cleanup_tests = [
        "tests/test_server_cleanup.py",
        "tests/test_error_handling.py"
    ]
    
    cli_tests = [
        "test_client_behavior.py",
        "test_fixed_client.py",
    ]

    shell_tests = [
        "./test-readme-examples.sh",
        "./test-cli-examples.sh",
        "./test-server-specific.sh",
    ]
    
    # Default to core and cleanup tests
    pytest_args = []
    pytest_args.extend(core_tests)
    pytest_args.extend(cleanup_tests)

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
        # Use the dedicated NPX tests files
        pytest_args = npx_tests
        args.remove("--npx-only")

    if "--python-only" in args:
        # Only include test_servers.py and filter for Python
        pytest_args = ["tests/test_servers.py"]
        pytest_args.append("-k")
        pytest_args.append("python")
        args.remove("--python-only")
        
    if "--cleanup-only" in args:
        # Only run cleanup and error handling tests
        pytest_args = cleanup_tests
        args.remove("--cleanup-only")
        
    if "--filesystem-only" in args:
        # Only run filesystem server tests
        pytest_args = filesystem_tests
        args.remove("--filesystem-only")
        
    if "--transport-only" in args:
        # Only run transport tests
        pytest_args = transport_tests
        args.remove("--transport-only")

    if "--cli-only" in args:
        # Only run CLI-related tests
        pytest_args = cli_tests
        # Add shell script tests after running pytest
        args.remove("--cli-only")
        # Run shell tests after pytest
        shell_test_flag = True
        
    if "--shell-only" in args:
        # Only run shell script tests
        pytest_args = []  # Clear pytest args
        shell_test_flag = True
        args.remove("--shell-only")
        
    if "--all" in args:
        # Run all tests
        pytest_args = core_tests + npx_tests + additional_tests + filesystem_tests + transport_tests + cleanup_tests + cli_tests
        # Add shell script tests after running pytest
        shell_test_flag = True
        args.remove("--all")
        
    if "--skip-slow" in args:
        # Skip potentially slow or unreliable tests in CI
        pytest_args.append("-k")
        pytest_args.append("not test_playwright")
        args.remove("--skip-slow")

    # Add any remaining arguments
    pytest_args.extend(args)

    # Run pytest tests if args exist
    exit_code = 0
    if pytest_args:
        print(f"Running pytest tests with arguments: {pytest_args}")
        exit_code = pytest.main(pytest_args)
        
    # Run shell tests if needed
    if shell_test_flag:
        import subprocess
        import os
        
        # Make sure all shell scripts are executable
        for script in shell_tests:
            if os.path.exists(script):
                os.chmod(script, 0o755)
        
        print("\n=== Running shell script tests ===")
        for script in shell_tests:
            if os.path.exists(script):
                print(f"\nRunning {script}...")
                try:
                    result = subprocess.run(script, shell=True, check=False)
                    if result.returncode != 0:
                        print(f"Shell test {script} failed with exit code {result.returncode}")
                        exit_code = result.returncode
                except Exception as e:
                    print(f"Error running {script}: {e}")
                    exit_code = 1
            else:
                print(f"Script {script} not found, skipping")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()