#!/bin/bash

# Source the autopilot functions
source /home/fiod/stock-pick/ChatGPT-Micro-Cap-Experiment/autopilot.sh

echo "=== DEMONSTRATING VERBOSE MODE ==="
echo ""

echo "1. Testing run_cmd with VERBOSE=0 (normal mode):"
VERBOSE=0
run_cmd "echo 'This is a test command'"
echo ""

echo "2. Testing run_cmd with VERBOSE=1 (verbose mode):"
VERBOSE=1  
run_cmd "echo 'This is a verbose test command'"
echo ""

echo "3. Testing run_cmd with a failing command (verbose mode):"
run_cmd "nonexistent_command_test"
echo ""

echo "4. Testing trace function:"
trace "This is a trace message that only shows in verbose mode"
echo ""

echo "Demo complete!"