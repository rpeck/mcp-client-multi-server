#!/usr/bin/env python3
"""
Test script for process persistence on macOS.
"""

import os
import sys
import subprocess
import time
import psutil
import signal

print("Testing process persistence")
print("-" * 50)

# Ensure log directory exists
log_dir = os.path.expanduser("~/temp_logs")
os.makedirs(log_dir, exist_ok=True)

# Create log files
timestamp = time.strftime("%Y%m%d-%H%M%S")
stdout_log = os.path.join(log_dir, f"test_{timestamp}_stdout.log")
stderr_log = os.path.join(log_dir, f"test_{timestamp}_stderr.log")

print(f"Log files: {stdout_log}, {stderr_log}")

# Open log files
stdout_file = open(stdout_log, "w")
stderr_file = open(stderr_log, "w")

# Test different process launching methods
if len(sys.argv) > 1 and sys.argv[1] == "nohup":
    print("Using nohup method")
    cmd = ["nohup", "python", "examples/echo_server.py"]
    method = "nohup"
elif len(sys.argv) > 1 and sys.argv[1] == "setpgrp":
    print("Using setpgrp method")
    cmd = ["python", "examples/echo_server.py"]
    method = "setpgrp"
elif len(sys.argv) > 1 and sys.argv[1] == "session":
    print("Using start_new_session method")
    cmd = ["python", "examples/echo_server.py"]
    method = "session"
else:
    print("Using combined method")
    cmd = ["nohup", "python", "examples/echo_server.py"]
    method = "combined"

print(f"Launching command: {' '.join(cmd)}")

# Launch the process with appropriate method
if method == "nohup":
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=stdout_file,
        stderr=stderr_file,
        text=True,
        bufsize=0
    )
elif method == "setpgrp":
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=stdout_file,
        stderr=stderr_file,
        text=True,
        bufsize=0,
        preexec_fn=os.setpgrp
    )
elif method == "session":
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=stdout_file,
        stderr=stderr_file,
        text=True,
        bufsize=0,
        start_new_session=True
    )
else:  # combined
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=stdout_file,
        stderr=stderr_file,
        text=True,
        bufsize=0,
        start_new_session=True,
        preexec_fn=os.setpgrp
    )

print(f"Process started with PID: {process.pid}")

# Store process info
pid = process.pid
pgid = os.getpgid(pid) if hasattr(os, 'getpgid') else None
print(f"Process group ID: {pgid}")

# Wait for process to start
time.sleep(2)

# Check if process is running
try:
    os.kill(pid, 0)
    print(f"Process {pid} is running after launch")
except OSError:
    print(f"Process {pid} is NOT running after launch")

# For testing, actually kill the process now
try:
    if method in ["setpgrp", "combined"]:
        # Kill the entire process group
        print(f"Killing process group {pgid}")
        os.killpg(pgid, signal.SIGTERM)
    else:
        # Kill just the process
        print(f"Killing process {pid}")
        os.kill(pid, signal.SIGTERM)
    
    print("Process terminated")
except Exception as e:
    print(f"Error terminating process: {e}")

# Close log files
stdout_file.close()
stderr_file.close()

print("-" * 50)
print("Test completed")