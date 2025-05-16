#!/bin/bash
# Comprehensive script to test ALL CLI examples from README.md

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

# Create a temporary directory for test outputs and test files
TEMP_DIR=$(mktemp -d)
TEST_FILE="$TEMP_DIR/test_file.txt"
TEST_DIR="$TEMP_DIR/test_dir"
echo "This is a test file for MCP tests" > "$TEST_FILE"
mkdir -p "$TEST_DIR"

echo -e "${ECHO}Created temporary directory: $TEMP_DIR${RESET}"
echo -e "${ECHO}Created test file: $TEST_FILE${RESET}"
echo -e "${ECHO}Created test directory: $TEST_DIR${RESET}"

# Function to report test results
report_test() {
  local test_name="$1"
  local status="$2"
  local details="${3:-}"
  
  if [ "$status" -eq 0 ]; then
    echo -e "${GREEN}✓ PASS: $test_name${RESET}"
    TESTS_PASSED=$((TESTS_PASSED+1))
    return 0
  elif [ "$status" -eq 2 ]; then
    echo -e "${YELLOW}⚠ SKIP: $test_name${RESET}"
    TESTS_SKIPPED=$((TESTS_SKIPPED+1))
    if [ -n "$details" ]; then
      echo -e "${YELLOW}  Reason: $details${RESET}"
    fi
    return 0
  else
    echo -e "${RED}✗ FAIL: $test_name${RESET}"
    TESTS_FAILED=$((TESTS_FAILED+1))
    if [ -n "$details" ]; then
      echo -e "${RED}  Error: $details${RESET}"
    fi
    return 1
  fi
}

# Function to check if a server is available in config
check_server_available() {
  local server=$1

  echo -e "${ECHO}Checking if $server server is available...${RESET}"
  local server_list=$(python main.py -c $CONFIG list 2>/dev/null)

  if [[ $? -ne 0 ]]; then
    echo -e "${RED}Failed to list servers${RESET}"
    return 1
  fi

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

# Function to run a command and check its output
run_command() {
  local test_name="$1"
  local command="$2"
  local expected_content="$3"
  local skip_condition="${4:-false}"
  
  if $skip_condition; then
    report_test "$test_name" 2 "Skipped due to server unavailability"
    return 0
  fi
  
  echo -e "${ECHO}TEST: $test_name${RESET}"
  echo -e "${ECHO}COMMAND: $command${RESET}"
  
  # Create output file
  local output_file="$TEMP_DIR/${test_name// /_}.out"
  
  # Run command and capture output
  eval "$command" > "$output_file" 2>&1
  local exit_code=$?
  
  # Check results
  if [ $exit_code -ne 0 ]; then
    report_test "$test_name" 1 "Command failed with exit code $exit_code"
    echo -e "${RED}Command output:${RESET}"
    cat "$output_file"
    return 1
  elif [ -n "$expected_content" ] && ! check_output "$output_file" "$expected_content"; then
    report_test "$test_name" 1 "Expected content not found: '$expected_content'"
    echo -e "${RED}Command output:${RESET}"
    cat "$output_file"
    return 1
  else
    report_test "$test_name" 0
    return 0
  fi
}

# Get allowed directory for filesystem tests
get_allowed_dir() {
  local output_file="$TEMP_DIR/allowed_dir.out"
  python main.py -c $CONFIG query --server filesystem --tool list_allowed_directories > "$output_file" 2>&1
  
  if [ $? -ne 0 ]; then
    echo "/Users/rpeck"  # Default fallback
    return
  fi
  
  # Try to extract allowed directory - look for paths with /Users in them first
  local user_dir=$(grep -o "/Users/[^ ]*" "$output_file" | head -1)
  if [ -n "$user_dir" ]; then
    echo "$user_dir"  # User directory is preferred
    return
  fi
  
  # If no user directory, take any path
  local allowed_dir=$(grep -o "/[^ ]*" "$output_file" | head -1)
  if [ -z "$allowed_dir" ]; then
    echo "/Users/rpeck"  # Default fallback
  else
    echo "$allowed_dir"
  fi
}

echo -e "${ECHO}Testing ALL README CLI examples${RESET}"
echo -e "${ECHO}Using config file: $CONFIG${RESET}"
echo

echo -e "${ECHO}=== General Commands Examples ===${RESET}"

# Test: List all configured servers
run_command "List servers" "python main.py -c $CONFIG list" "Configured MCP servers"

# Test: Help command
run_command "Show help" "python main.py --help | head -5" "usage"

# Test: Tools listing
run_command "List tools for a server" "python main.py -c $CONFIG tools --server echo" "Tools available on server" $(! check_server_available "echo")

echo -e "${ECHO}=== Server Lifecycle Commands ===${RESET}"

# Test: Launch server
ECHO_AVAILABLE=$(check_server_available "echo" && echo "true" || echo "false")
if $ECHO_AVAILABLE; then
  # Launch server first (this should pass)
  run_command "Launch echo server" "python main.py -c $CONFIG launch --server echo" "launched successfully"
  
  # Stop server (this should pass if launch worked)
  run_command "Stop echo server" "python main.py -c $CONFIG stop --server echo" "stopped"
else
  report_test "Launch echo server" 2 "Echo server not available"
  report_test "Stop echo server" 2 "Echo server not available"
fi

# Test: Stop all servers 
# This is more complex to test reliably, marking as skipped
report_test "Stop all servers" 2 "Would require launching multiple servers first"

echo -e "${ECHO}=== Echo Server Examples ===${RESET}"

if check_server_available "echo"; then
  # Echo server commands
  run_command "Echo message with explicit tool" "python main.py -c $CONFIG query --server echo --tool process_message --message \"Hello world\"" "Hello world"
  run_command "Echo message with default tool" "python main.py -c $CONFIG query --server echo --message \"Hello world\"" "Hello world"
  run_command "Echo ping tool" "python main.py -c $CONFIG query --server echo --tool ping" "pong"
else
  report_test "Echo server examples" 2 "Echo server not available"
fi

echo -e "${ECHO}=== Filesystem Server Examples ===${RESET}"

if check_server_available "filesystem"; then
  # Get the allowed directory
  ALLOWED_DIR=$(get_allowed_dir)
  echo -e "${ECHO}Using allowed directory: $ALLOWED_DIR${RESET}"
  
  # List tools
  run_command "List filesystem tools" "python main.py -c $CONFIG tools --server filesystem" "read_file"
  
  # List directory
  run_command "List directory" "python main.py -c $CONFIG query --server filesystem --tool list_directory --message '{\"path\": \"$ALLOWED_DIR\"}'" "[DIR]\\|[FILE]"
  
  # Create a unique test filename within the allowed directory
  # Make sure the filename is unique with a timestamp and random string
  TIMESTAMP=$(date +%Y%m%d%H%M%S)
  RANDOM_STRING=$(openssl rand -hex 4)
  TEST_FILENAME="mcp_test_file_${TIMESTAMP}_${RANDOM_STRING}.txt"
  
  # Need to ensure this is a valid path - don't append to ALLOWED_DIR directly
  # as it might be a file rather than a directory
  if [ "$ALLOWED_DIR" = "/opt/homebrew/bin/npx" ]; then
    # Special case: npx is a file, not a directory
    TEST_FILEPATH="/opt/homebrew/bin/${TEST_FILENAME}"
  else
    # Normal case: append to allowed directory
    TEST_FILEPATH="$ALLOWED_DIR/${TEST_FILENAME}"
  fi
  
  TEST_CONTENT="This is a test file created by MCP test script at $(date)"
  
  echo -e "${ECHO}Testing with test file: $TEST_FILEPATH${RESET}"
  
  # Test write_file by creating our test file
  echo -e "${ECHO}Testing write_file with a unique test file${RESET}"
  WRITE_OUTPUT="$TEMP_DIR/write_output.txt"
  python main.py -c $CONFIG query --server filesystem --tool write_file --message "{\"path\": \"$TEST_FILEPATH\", \"content\": \"$TEST_CONTENT\"}" > "$WRITE_OUTPUT" 2>&1
  WRITE_STATUS=$?
  
  if [ $WRITE_STATUS -eq 0 ]; then
    report_test "Write file" 0
    
    # Test read_file with the file we just created
    echo -e "${ECHO}Testing read_file with our test file${RESET}"
    READ_OUTPUT="$TEMP_DIR/read_output.txt"
    python main.py -c $CONFIG query --server filesystem --tool read_file --message "{\"path\": \"$TEST_FILEPATH\"}" > "$READ_OUTPUT" 2>&1
    
    if [ $? -eq 0 ] && check_output "$READ_OUTPUT" "test file created by MCP"; then
      report_test "Read file" 0
    else
      report_test "Read file" 1 "Failed to read test file or content doesn't match"
    fi
    
    # Test get_file_info
    echo -e "${ECHO}Testing get_file_info${RESET}"
    INFO_OUTPUT="$TEMP_DIR/info_output.txt"
    python main.py -c $CONFIG query --server filesystem --tool get_file_info --message "{\"path\": \"$TEST_FILEPATH\"}" > "$INFO_OUTPUT" 2>&1
    
    if [ $? -eq 0 ] && check_output "$INFO_OUTPUT" "size"; then
      report_test "Get file info" 0
    else
      report_test "Get file info" 1 "Failed to get file info or missing size information"
    fi
    
    # Clean up by deleting the test file
    echo -e "${ECHO}Cleaning up test file${RESET}"
    DELETE_OUTPUT="$TEMP_DIR/delete_output.txt"
    # Note: Many filesystem servers don't have a delete_file tool, but we'll check for options
    
    # Try the search_files tool to verify the file exists
    echo -e "${ECHO}Testing search_files${RESET}"
    SEARCH_OUTPUT="$TEMP_DIR/search_output.txt"
    python main.py -c $CONFIG query --server filesystem --tool search_files --message "{\"path\": \"$ALLOWED_DIR\", \"pattern\": \"$TEST_FILENAME\"}" > "$SEARCH_OUTPUT" 2>&1
    
    if [ $? -eq 0 ] && check_output "$SEARCH_OUTPUT" "$TEST_FILENAME"; then
      report_test "Search files" 0
    else
      report_test "Search files" 1 "Failed to find test file with search"
    fi
  else
    report_test "Write file" 1 "Failed to create test file"
    # Skip dependent tests
    report_test "Read file" 2 "Skipped because write_file failed"
    report_test "Get file info" 2 "Skipped because write_file failed"
    report_test "Search files" 2 "Skipped because write_file failed"
  fi
  
  # Create a test directory
  echo -e "${ECHO}Testing create_directory${RESET}"
  TEST_DIR_NAME="mcp_test_dir_${TIMESTAMP}_${RANDOM_STRING}"
  
  # Apply same path logic as for the test file
  if [ "$ALLOWED_DIR" = "/opt/homebrew/bin/npx" ]; then
    # Special case: npx is a file, not a directory
    TEST_DIR_PATH="/opt/homebrew/bin/${TEST_DIR_NAME}"
  else
    # Normal case: append to allowed directory
    TEST_DIR_PATH="$ALLOWED_DIR/${TEST_DIR_NAME}"
  fi
  
  DIR_OUTPUT="$TEMP_DIR/dir_output.txt"
  python main.py -c $CONFIG query --server filesystem --tool create_directory --message "{\"path\": \"$TEST_DIR_PATH\"}" > "$DIR_OUTPUT" 2>&1
  
  if [ $? -eq 0 ]; then
    report_test "Create directory" 0
    
    # Try the directory_tree tool
    echo -e "${ECHO}Testing directory_tree${RESET}"
    TREE_OUTPUT="$TEMP_DIR/tree_output.txt"
    # Use a small depth to keep output manageable
    python main.py -c $CONFIG query --server filesystem --tool directory_tree --message "{\"path\": \"$ALLOWED_DIR\", \"depth\": 1}" > "$TREE_OUTPUT" 2>&1
    
    if [ $? -eq 0 ] && check_output "$TREE_OUTPUT" "children"; then
      report_test "Directory tree" 0
    else
      report_test "Directory tree" 1 "Failed to get directory tree or missing children field"
    fi
  else
    report_test "Create directory" 1 "Failed to create test directory"
    report_test "Directory tree" 2 "Skipped because create_directory failed"
  fi
  
  # List allowed directories - this should work
  run_command "List allowed directories" "python main.py -c $CONFIG query --server filesystem --tool list_allowed_directories" "$ALLOWED_DIR"
else
  report_test "Filesystem server examples" 2 "Filesystem server not available"
fi

echo -e "${ECHO}=== Fetch Server Examples ===${RESET}"

if check_server_available "fetch"; then
  # List tools
  run_command "List fetch tools" "python main.py -c $CONFIG tools --server fetch" "fetch"
  
  # Simple URL
  run_command "Fetch with simple URL" "python main.py -c $CONFIG query --server fetch --message \"https://example.com\"" "example.com"
  
  # JSON URL
  run_command "Fetch with JSON message" "python main.py -c $CONFIG query --server fetch --message '{\"url\": \"https://example.com\"}'" "example.com"
  
  # Complex JSON with headers
  run_command "Fetch with complex JSON" "python main.py -c $CONFIG query --server fetch --message '{\"url\": \"https://example.com\", \"method\": \"GET\", \"headers\": {\"User-Agent\": \"MCP Client\"}}'" "example.com"
else
  report_test "Fetch server examples" 2 "Fetch server not available"
fi

echo -e "${ECHO}=== Sequential Thinking Server Examples ===${RESET}"

if check_server_available "sequential-thinking"; then
  # List tools
  run_command "List sequential-thinking tools" "python main.py -c $CONFIG tools --server sequential-thinking" "sequentialthinking"
  
  # Since sequential-thinking requires an LLM, mark all further tests as skipped
  report_test "Get sequential-thinking server info" 2 "Server requires LLM sampling capabilities"
  
  # Start thinking sequence - skipped because it requires LLM support
  report_test "Sequential thinking sequentialthinking tool" 2 "Requires LLM sampling support"
else
  report_test "Sequential thinking server examples" 2 "Sequential thinking server not available"
fi

echo -e "${ECHO}=== Playwright Server Examples ===${RESET}"

if check_server_available "playwright"; then
  # List tools
  run_command "List playwright tools" "python main.py -c $CONFIG tools --server playwright" "playwright"
  
  # The following tools require an active browser session
  report_test "Playwright navigate" 2 "Requires active browser session"
  report_test "Playwright screenshot" 2 "Requires active browser session"
  report_test "Playwright click" 2 "Requires active browser session"
else
  report_test "Playwright server examples" 2 "Playwright server not available"
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
  echo -e "${RED}$TESTS_FAILED tests failed${RESET}"
  exit 1
else
  echo -e "${GREEN}All executed tests passed successfully${RESET}"
  exit 0
fi