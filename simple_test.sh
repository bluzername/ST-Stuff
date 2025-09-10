#!/bin/bash
echo "=== TESTING FIXES ==="
echo ""
echo "1. Script path regex fix:"
cmd="/venv/bin/python -u script_name.py --check"
script_file=$(echo "$cmd" | grep -oE '[^ ]+\.py' | head -1)
echo "Command: $cmd"
echo "Extracted: $script_file"
echo ""
echo "2. Current ET time:"
TZ='America/New_York' date '+%H:%M on %Y-%m-%d'
echo ""
echo "3. Status (if autopilot running):"
./autopilot.sh status 2>/dev/null || echo "Autopilot not running"