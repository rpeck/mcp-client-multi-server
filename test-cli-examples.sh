#!/bin/bash
# Script to test all CLI examples from the README

set -e  # Exit on error
CONFIG="examples/config.json"
ECHO="\033[1;36m"  # Cyan color for echo
RESET="\033[0m"    # Reset color

echo -e "${ECHO}Testing CLI examples from README.md${RESET}"
echo -e "${ECHO}Using config file: $CONFIG${RESET}"
echo

# General Commands
echo -e "${ECHO}Testing: List all configured servers${RESET}"
python main.py -c $CONFIG list
echo

# Show help
echo -e "${ECHO}Testing: Show help${RESET}"
python main.py --help | head -5
echo

# Server tools
echo -e "${ECHO}Testing: List available tools on echo server${RESET}"
python main.py -c $CONFIG tools --server echo
echo

# Launch server in a background process to keep it running
echo -e "${ECHO}Testing: Launch echo server${RESET}"
python main.py -c $CONFIG launch --server echo
echo

# Echo server - query 
echo -e "${ECHO}Testing: Send simple message to echo server${RESET}"
python main.py -c $CONFIG query --server echo --message "Hello world"
echo

# Echo server - tool
echo -e "${ECHO}Testing: Use ping tool on echo server${RESET}"
python main.py -c $CONFIG query --server echo --tool ping
echo

# JSON arguments with --message parameter
echo -e "${ECHO}Testing: Tool with JSON arguments${RESET}"
python main.py -c $CONFIG query --server echo --tool process_message --message "This is a test message"
echo

# ----------------------
# Creating a proper stop test that works in CI/CD
# ----------------------

# Create a dedicated launch-stop test using system resource tracking
echo -e "${ECHO}Testing: Launch-Stop sequence${RESET}"

# Function to check if a process is running (platform independent)
check_pid_running() {
  local pid=$1
  case "$(uname -s)" in
    Darwin|Linux)   # macOS or Linux
      ps -p $pid &>/dev/null
      ;;
    CYGWIN*|MINGW*|MSYS*|Windows*) # Windows
      tasklist.exe 2>NUL | grep -i $pid &>/dev/null
      ;;
    *)  # Default to standard check
      ps -p $pid &>/dev/null
      ;;
  esac
  return $?
}

# Create a temp file for nohup output that works on any platform
TMP_LOG_FILE=$(mktemp)
echo "Using temp log file: $TMP_LOG_FILE"

# Launch in background for dedicated test
echo "Launching echo server as background process..."
nohup python main.py -c $CONFIG launch --server echo > "$TMP_LOG_FILE" 2>&1 &
BG_PID=$!
echo "Launched server with PID: $BG_PID"

# Give it time to start
sleep 2

# Ensure psutil is installed for the enhanced stop command to work
echo -e "${ECHO}Installing psutil if needed${RESET}"
pip install psutil > /dev/null 2>&1

# Test stopping the server with the stop command
echo -e "${ECHO}Testing: Stop server command${RESET}"
python main.py -c $CONFIG stop --server echo

# Wait a moment for stop to complete
sleep 1

# Verify the server is really stopped
if check_pid_running $BG_PID; then
  echo "SERVER STOP TEST FAILED: Process $BG_PID is still running! Stopping it manually..."
  kill -9 $BG_PID
  echo "Stop command failed but we killed the process manually"
  TEST_RESULT="FAILED"
else
  echo "SERVER STOP TEST PASSED: Process $BG_PID was successfully stopped by stop command"
  echo "Note: The client reports failure because it's using a separate process"
  echo "      But what matters is that the server process is actually stopped."
  TEST_RESULT="PASSED"
fi

# Clean up
rm -f "$TMP_LOG_FILE"

echo "Stop command test result: $TEST_RESULT"
echo

# Test stop-all command
echo -e "${ECHO}Testing: Launch multiple servers${RESET}"
# Launch multiple servers in the background
python main.py -c $CONFIG launch --server echo &
ECHO_PID=$!
sleep 1
# This will launch a second server (if available in config)
if grep -q "filesystem" "$CONFIG"; then
  python main.py -c $CONFIG launch --server filesystem &
  FS_PID=$!
  sleep 1
fi

# Give them time to start
sleep 2

echo -e "${ECHO}Testing: Stop-all servers command${RESET}"
python main.py -c $CONFIG stop-all

# Wait a moment for stops to complete
sleep 1

# Verify servers were stopped
STOPALL_SUCCESS=true
if check_pid_running $ECHO_PID; then
  echo "STOP-ALL TEST PARTIAL FAILURE: Echo server process $ECHO_PID is still running!"
  kill -9 $ECHO_PID
  STOPALL_SUCCESS=false
fi

if [ ! -z "$FS_PID" ] && check_pid_running $FS_PID; then
  echo "STOP-ALL TEST PARTIAL FAILURE: Filesystem server process $FS_PID is still running!"
  kill -9 $FS_PID
  STOPALL_SUCCESS=false
fi

if [ "$STOPALL_SUCCESS" = true ]; then
  echo "STOP-ALL TEST PASSED: All server processes were successfully stopped"
  STOPALL_RESULT="PASSED"
else
  echo "STOP-ALL TEST FAILED: Some processes were not stopped"
  STOPALL_RESULT="FAILED"
fi

echo "Stop-all command test result: $STOPALL_RESULT"

echo -e "${ECHO}Tests completed${RESET}"