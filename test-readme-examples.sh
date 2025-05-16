#!/bin/bash
# Script to test the CLI examples from README.md

set -e  # Exit on error
CONFIG="examples/config.json"
ECHO="\033[1;36m"  # Cyan color for echo
RESET="\033[0m"    # Reset color
GREEN="\033[1;32m"  # Green color for success
RED="\033[1;31m"    # Red color for failure
YELLOW="\033[1;33m" # Yellow color for warnings

# Track test success/failure
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Create a temporary directory for test outputs
TEMP_DIR=$(mktemp -d)
echo -e "${ECHO}Created temporary directory: $TEMP_DIR${RESET}"

# Function to report test results
report_test() {
  local test_name="$1"
  local status="$2"
  
  if [ "$status" -eq 0 ]; then
    echo -e "${GREEN}✓ PASS: $test_name${RESET}"
    TESTS_PASSED=$((TESTS_PASSED+1))
    return 0
  elif [ "$status" -eq 2 ]; then
    echo -e "${YELLOW}⚠ SKIP: $test_name${RESET}"
    TESTS_SKIPPED=$((TESTS_SKIPPED+1))
    return 0
  else
    echo -e "${RED}✗ FAIL: $test_name${RESET}"
    TESTS_FAILED=$((TESTS_FAILED+1))
    return 1
  fi
}

# Function to check if a server is available in config
check_server_available() {
  local server=$1

  echo -e "${ECHO}Checking if $server server is available...${RESET}"
  server_list=$(python main.py -c $CONFIG list)

  if [[ $server_list == *"$server"* ]]; then
    echo -e "${GREEN}$server server is available in config${RESET}"
    return 0
  else
    echo -e "${RED}$server server is not found in config${RESET}"
    return 1
  fi
}

# Function to check if output contains expected content
check_output() {
  local output_file=$1
  local expected_content=$2
  
  if grep -q "$expected_content" "$output_file"; then
    return 0
  else
    return 1
  fi
}

echo -e "${ECHO}Testing all README CLI examples${RESET}"
echo -e "${ECHO}Using config file: $CONFIG${RESET}"
echo

# General Commands
echo -e "${ECHO}=== General Commands Examples ===${RESET}"

# Test: List all configured servers
echo -e "${ECHO}TEST: List all configured servers${RESET}"
LIST_OUTPUT="$TEMP_DIR/list_output.txt"
python main.py -c $CONFIG list > "$LIST_OUTPUT" 2>&1
if [ $? -eq 0 ] && check_output "$LIST_OUTPUT" "Configured MCP servers"; then
  report_test "List servers" 0
else
  report_test "List servers" 1
fi

# Test: List tools on a server
echo -e "${ECHO}TEST: List tools on echo server${RESET}"
if check_server_available "echo"; then
  TOOLS_OUTPUT="$TEMP_DIR/tools_output.txt"
  python main.py -c $CONFIG tools --server echo > "$TOOLS_OUTPUT" 2>&1
  if [ $? -eq 0 ] && check_output "$TOOLS_OUTPUT" "Tools available on server"; then
    report_test "List tools" 0
  else
    report_test "List tools" 1
  fi
else
  report_test "List tools" 2
fi

echo -e "${ECHO}=== Echo Server Examples ===${RESET}"

# Echo Server example
if check_server_available "echo"; then
  # Test: Send a simple message to echo server
  echo -e "${ECHO}TEST: Send a simple message to echo server${RESET}"
  ECHO_OUTPUT="$TEMP_DIR/echo_output.txt"
  python main.py -c $CONFIG query --server echo --message "Hello world" > "$ECHO_OUTPUT" 2>&1
  if [ $? -eq 0 ] && check_output "$ECHO_OUTPUT" "Hello world"; then
    report_test "Echo simple message" 0
  else
    report_test "Echo simple message" 1
  fi

  # Test: Use ping tool
  echo -e "${ECHO}TEST: Use ping tool on echo server${RESET}"
  PING_OUTPUT="$TEMP_DIR/ping_output.txt"
  python main.py -c $CONFIG query --server echo --tool ping > "$PING_OUTPUT" 2>&1
  if [ $? -eq 0 ] && check_output "$PING_OUTPUT" "pong"; then
    report_test "Echo ping tool" 0
  else
    report_test "Echo ping tool" 1
  fi
else
  report_test "Echo server examples" 2
fi

echo -e "${ECHO}=== Filesystem Server Examples ===${RESET}"

# Filesystem Server example
if check_server_available "filesystem"; then
  # Get the allowed directory
  ALLOWED_DIR_OUTPUT="$TEMP_DIR/allowed_dir_output.txt"
  python main.py -c $CONFIG query --server filesystem --tool list_allowed_directories > "$ALLOWED_DIR_OUTPUT" 2>&1
  ALLOWED_DIR=$(grep -o "/[^ ]*" "$ALLOWED_DIR_OUTPUT" | head -1)
  
  if [ -z "$ALLOWED_DIR" ]; then
    ALLOWED_DIR="/Users/rpeck"  # Default to a likely allowed path
  fi
  
  echo -e "${ECHO}Using allowed directory: $ALLOWED_DIR${RESET}"
  
  # Test: List directory with JSON message
  echo -e "${ECHO}TEST: List directory with JSON message${RESET}"
  LIST_DIR_OUTPUT="$TEMP_DIR/list_dir_output.txt"
  python main.py -c $CONFIG query --server filesystem --tool list_directory --message "{\"path\": \"$ALLOWED_DIR\"}" > "$LIST_DIR_OUTPUT" 2>&1
  if [ $? -eq 0 ] && (check_output "$LIST_DIR_OUTPUT" "[FILE]" || check_output "$LIST_DIR_OUTPUT" "[DIR]"); then
    report_test "Filesystem list directory with JSON" 0
  else
    report_test "Filesystem list directory with JSON" 1
  fi
  
  # Other filesystem tests would go here
else
  report_test "Filesystem server examples" 2
fi

echo -e "${ECHO}=== Fetch Server Examples ===${RESET}"

# Fetch Server example
if check_server_available "fetch"; then
  # Test: Fetch with simple URL
  echo -e "${ECHO}TEST: Fetch with simple URL${RESET}"
  FETCH_OUTPUT="$TEMP_DIR/fetch_output.txt"
  python main.py -c $CONFIG query --server fetch --message "https://example.com" > "$FETCH_OUTPUT" 2>&1
  if [ $? -eq 0 ] && check_output "$FETCH_OUTPUT" "example.com"; then
    report_test "Fetch with simple URL" 0
  else
    report_test "Fetch with simple URL" 1
  fi

  # Test: Fetch with JSON message
  echo -e "${ECHO}TEST: Fetch with JSON message${RESET}"
  FETCH_JSON_OUTPUT="$TEMP_DIR/fetch_json_output.txt"
  python main.py -c $CONFIG query --server fetch --message '{"url": "https://example.com"}' > "$FETCH_JSON_OUTPUT" 2>&1
  if [ $? -eq 0 ] && check_output "$FETCH_JSON_OUTPUT" "example.com"; then
    report_test "Fetch with JSON message" 0
  else
    report_test "Fetch with JSON message" 1
  fi

  # Test: Fetch with complex JSON
  echo -e "${ECHO}TEST: Fetch with complex JSON message${RESET}"
  FETCH_COMPLEX_OUTPUT="$TEMP_DIR/fetch_complex_output.txt"
  python main.py -c $CONFIG query --server fetch --message '{"url": "https://example.com", "method": "GET", "headers": {"User-Agent": "MCP Client"}}' > "$FETCH_COMPLEX_OUTPUT" 2>&1
  if [ $? -eq 0 ] && check_output "$FETCH_COMPLEX_OUTPUT" "example.com"; then
    report_test "Fetch with complex JSON" 0
  else
    report_test "Fetch with complex JSON" 1
  fi
else
  report_test "Fetch server examples" 2
fi

# Print test summary
echo -e "${ECHO}=== Test Summary ===${RESET}"
echo -e "${GREEN}Tests passed: $TESTS_PASSED${RESET}"
echo -e "${RED}Tests failed: $TESTS_FAILED${RESET}"
echo -e "${YELLOW}Tests skipped: $TESTS_SKIPPED${RESET}"

# Clean up temporary directory
echo -e "${ECHO}Cleaning up temporary directory${RESET}"
rm -rf "$TEMP_DIR"

# Exit with error if any tests failed
if [ $TESTS_FAILED -gt 0 ]; then
  echo -e "${RED}Some tests failed${RESET}"
  exit 1
else
  echo -e "${GREEN}All executed tests passed successfully${RESET}"
  exit 0
fi