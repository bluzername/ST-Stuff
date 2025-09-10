#!/bin/bash

echo "=== TESTING AUTOPILOT FIXES ==="
echo ""

# Source the functions
source /home/fiod/stock-pick/ChatGPT-Micro-Cap-Experiment/autopilot.sh

echo "1. Testing next action calculation:"
show_next_action
echo ""

echo "2. Testing script path regex fix:"
VERBOSE=0  # Test without verbose mode first
cmd="python /path/with spaces/test script.py --arg"
echo "Test command: $cmd"
script_file=$(echo "$cmd" | grep -oE '[^ ]+\.py' | head -1)
echo "Extracted script: $script_file"
echo ""

echo "3. Testing status command:"
./autopilot.sh status
echo ""

echo "4. Testing diagnose command (first 15 lines):"
./autopilot.sh diagnose | head -15
echo ""

echo "All fixes tested!"