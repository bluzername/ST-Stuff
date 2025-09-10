#!/bin/bash
#
# ChatGPT Trading Pipeline Autopilot
# 
# One script to rule them all. No systemd bullshit, no cron nonsense.
# Just a simple loop that does what it's supposed to do, when it's supposed to do it.
#
# Author: The guy who thinks your scheduler is broken
# License: DGAF (Do Generally As you Feel)

set -euo pipefail  # Because we're not amateurs

# Virtual environment activation
VENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/venv"
if [[ -d "$VENV_DIR" ]]; then
    source "$VENV_DIR/bin/activate"
fi

# Configuration - Because hardcoding is for idiots
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/autopilot.log"
STATE_FILE="$SCRIPT_DIR/.autopilot.state"
LOCK_FILE="$SCRIPT_DIR/.autopilot.lock"
WEB_MONITOR_PID_FILE="$SCRIPT_DIR/.web_monitor.pid"
CONFIG_FILE="$SCRIPT_DIR/.autopilot.config"

# Verbose mode - Set VERBOSE=1 to see everything
VERBOSE=${VERBOSE:-0}

# Portfolio paths
PORTFOLIO_FILE="Scripts and CSV Files/chatgpt_portfolio_update.csv"
IB_DIR="$SCRIPT_DIR/ib_trading"
WEB_DIR="$SCRIPT_DIR/web_monitor"

# Time settings (Eastern Time - because that's what markets use)
DAILY_UPDATE_TIME="16:15"  # 4:15 PM ET - After market close
EXECUTE_TRADES_TIME="09:15" # 9:15 AM ET - Before market open

# Logging function - Because printf debugging is for beginners
log() {
    local level="$1"
    shift
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $*" | tee -a "$LOG_FILE"
}

error() { log "ERROR" "$@"; }
info() { log "INFO" "$@"; }
debug() { log "DEBUG" "$@"; }

# Structured logging functions - Route to unified pipeline logger
pipeline_logger="$SCRIPT_DIR/shell_logger.py"

pipeline_log_startup() {
    local component="$1"
    local details="$2"
    if [[ -x "$pipeline_logger" ]]; then
        source "$VENV_DIR/bin/activate" 2>/dev/null
        "$pipeline_logger" startup "$component" "$details" 2>/dev/null
    fi
}

pipeline_log_action() {
    local category="$1"
    local action="$2" 
    local details="$3"
    if [[ -x "$pipeline_logger" ]]; then
        source "$VENV_DIR/bin/activate" 2>/dev/null
        "$pipeline_logger" action "$category" "$action" "$details" 2>/dev/null
    fi
}

pipeline_log_exec_start() {
    local exec_id="$1"
    if [[ -x "$pipeline_logger" && -n "$exec_id" ]]; then
        source "$VENV_DIR/bin/activate" 2>/dev/null
        "$pipeline_logger" exec_start "$exec_id" 2>/dev/null
    fi
}

pipeline_log_exec_complete() {
    local exec_id="$1"
    local duration_ms="$2"
    local result="$3"
    if [[ -x "$pipeline_logger" && -n "$exec_id" ]]; then
        source "$VENV_DIR/bin/activate" 2>/dev/null
        "$pipeline_logger" exec_complete "$exec_id" "$duration_ms" "$result" 2>/dev/null
    fi
}

pipeline_log_exec_failed() {
    local exec_id="$1" 
    local duration_ms="$2"
    local error_msg="$3"
    if [[ -x "$pipeline_logger" && -n "$exec_id" ]]; then
        source "$VENV_DIR/bin/activate" 2>/dev/null
        "$pipeline_logger" exec_failed "$exec_id" "$duration_ms" "$error_msg" 2>/dev/null
    fi
}

pipeline_log_error() {
    local category="$1"
    local message="$2" 
    local details="$3"
    if [[ -x "$pipeline_logger" ]]; then
        source "$VENV_DIR/bin/activate" 2>/dev/null
        "$pipeline_logger" error "$category" "$message" "$details" 2>/dev/null
    fi
}

pipeline_report_logs() {
    if [[ -x "$pipeline_logger" ]]; then
        source "$VENV_DIR/bin/activate" 2>/dev/null
        "$pipeline_logger" report_logs 2>/dev/null
    fi
}

# Verbose command execution - Shows everything that happens
run_cmd() {
    local cmd="$*"
    local start_time=$(date +%s)
    local start_ms=$(date +%s%3N)
    
    # Log command execution to structured logs
    local exec_id=$(pipeline_log_action "STARTUP" "Executing command: $cmd" "{\"cmd\": \"$cmd\", \"cwd\": \"$(pwd)\"}")
    [[ -n "$exec_id" ]] && pipeline_log_exec_start "$exec_id"
    
    if [[ $VERBOSE -eq 1 ]]; then
        info "EXEC: $cmd"
        info "CWD: $(pwd)"
        info "USER: $(whoami)"
        # Show just the first few PATH entries to avoid spam
        info "PATH: $(echo "$PATH" | cut -d: -f1-3):..."
    fi
    
    # Create temp files for stdout/stderr
    local stdout_file=$(mktemp)
    local stderr_file=$(mktemp)
    local exit_code
    
    # Execute command and capture everything
    if [[ $VERBOSE -eq 1 ]]; then
        # Verbose mode: show output in real-time AND log it
        eval "$cmd" 2>&1 | tee "$stdout_file"
        exit_code=${PIPESTATUS[0]}
    else
        # Normal mode: just capture for logging on error
        eval "$cmd" > "$stdout_file" 2> "$stderr_file"
        exit_code=$?
    fi
    
    local end_time=$(date +%s)
    local end_ms=$(date +%s%3N)
    local duration_ms=$((end_ms - start_ms))
    local duration=$((end_time - start_time))
    
    # Log structured execution results
    if [[ $exit_code -eq 0 ]]; then
        [[ -n "$exec_id" ]] && pipeline_log_exec_complete "$exec_id" "$duration_ms" "{\"exit_code\": $exit_code, \"duration_sec\": $duration}"
        if [[ $VERBOSE -eq 1 ]]; then
            info "SUCCESS: $cmd (exit: $exit_code, took: ${duration}s)"
        fi
    else
        [[ -n "$exec_id" ]] && pipeline_log_exec_failed "$exec_id" "$duration_ms" "Command failed with exit code $exit_code"
        pipeline_log_error "ERROR" "Command execution failed: $cmd" "{\"exit_code\": $exit_code, \"duration_sec\": $duration}"
        error "FAILED: $cmd (exit: $exit_code, took: ${duration}s)"
        error "STDOUT: $(cat "$stdout_file")"
        error "STDERR: $(cat "$stderr_file")"
        
        # Show file stats if it was a file operation
        if [[ "$cmd" == *".py"* ]]; then
            local script_file=$(echo "$cmd" | grep -oE '[^ ]+\.py' | head -1)
            if [[ -n "$script_file" ]]; then
                if [[ -f "$script_file" ]]; then
                    error "SCRIPT: $script_file exists, size: $(stat -c%s "$script_file") bytes, modified: $(stat -c%y "$script_file")"
                else
                    error "SCRIPT: $script_file NOT FOUND"
                    # Try to find what was actually intended
                    local py_files=$(echo "$cmd" | grep -oE '[^[:space:]]+\.py' | tr '\n' ' ')
                    if [[ -n "$py_files" ]]; then
                        error "DETECTED PY FILES: $py_files"
                    fi
                fi
            else
                error "SCRIPT: Could not extract Python script name from command: $cmd"
            fi
        fi
    fi
    
    # Cleanup
    rm -f "$stdout_file" "$stderr_file"
    
    return $exit_code
}

# Debug breadcrumb - only shows in verbose mode
trace() {
    [[ $VERBOSE -eq 1 ]] && info "TRACE: $*"
}

# Calculate and show next action
show_next_action() {
    local current_et_time current_et_date
    current_et_time=$(get_et_time)
    current_et_date=$(get_et_date)
    
    # Calculate seconds until next actions
    local daily_update_seconds trade_execution_seconds
    daily_update_seconds=$(calculate_seconds_until "$DAILY_UPDATE_TIME")
    trade_execution_seconds=$(calculate_seconds_until "$EXECUTE_TRADES_TIME")
    
    local next_action next_time next_seconds
    
    if [[ $daily_update_seconds -lt $trade_execution_seconds ]]; then
        next_action="Daily Portfolio Update"
        next_time="$DAILY_UPDATE_TIME"
        next_seconds=$daily_update_seconds
    else
        next_action="Trade Execution"
        next_time="$EXECUTE_TRADES_TIME"
        next_seconds=$trade_execution_seconds
    fi
    
    local hours minutes
    hours=$(( next_seconds / 3600 ))
    minutes=$(( (next_seconds % 3600) / 60 ))
    
    if [[ $next_seconds -lt 60 ]]; then
        info "NEXT ACTION: $next_action at $next_time ET (in ${next_seconds}s)"
    elif [[ $next_seconds -lt 3600 ]]; then
        info "NEXT ACTION: $next_action at $next_time ET (in ${minutes}m)"
    else
        info "NEXT ACTION: $next_action at $next_time ET (in ${hours}h ${minutes}m)"
    fi
}

# Calculate seconds until a given time (HH:MM format)
calculate_seconds_until() {
    local target_time="$1"
    local current_et_epoch target_et_epoch
    
    # Get current ET time in epoch
    current_et_epoch=$(TZ='America/New_York' date +%s)
    
    # Parse target time
    local target_hour target_minute
    target_hour=${target_time%:*}
    target_minute=${target_time#*:}
    
    # Get today's date in ET and construct target epoch
    local et_date
    et_date=$(TZ='America/New_York' date +%Y-%m-%d)
    target_et_epoch=$(TZ='America/New_York' date -d "$et_date $target_hour:$target_minute" +%s)
    
    # If target time has already passed today, calculate for tomorrow
    if [[ $target_et_epoch -le $current_et_epoch ]]; then
        target_et_epoch=$(TZ='America/New_York' date -d "$et_date $target_hour:$target_minute + 1 day" +%s)
    fi
    
    echo $(( target_et_epoch - current_et_epoch ))
}

# Signal handlers - Clean up your mess
cleanup() {
    info "Autopilot shutting down..."
    
    # Kill web monitor if we started it
    if [[ -f "$WEB_MONITOR_PID_FILE" ]]; then
        local pid
        pid=$(cat "$WEB_MONITOR_PID_FILE" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            info "Stopping web monitor (PID: $pid)"
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
        rm -f "$WEB_MONITOR_PID_FILE"
    fi
    
    # Remove lock file
    rm -f "$LOCK_FILE"
    info "Autopilot stopped"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Lock file management - Because running multiple instances is stupid
acquire_lock() {
    if [[ -f "$LOCK_FILE" ]]; then
        local existing_pid
        existing_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
            error "Autopilot already running with PID: $existing_pid"
            exit 1
        else
            info "Removing stale lock file"
            rm -f "$LOCK_FILE"
        fi
    fi
    
    echo $$ > "$LOCK_FILE"
    info "Lock acquired (PID: $$)"
}

# State management - Remember what we did
load_state() {
    if [[ -f "$STATE_FILE" ]]; then
        source "$STATE_FILE"
    fi
    
    # Initialize state variables if not set
    LAST_DAILY_UPDATE=${LAST_DAILY_UPDATE:-""}
    LAST_TRADE_EXECUTION=${LAST_TRADE_EXECUTION:-""}
}

save_state() {
    cat > "$STATE_FILE" << EOF
LAST_DAILY_UPDATE="$LAST_DAILY_UPDATE"
LAST_TRADE_EXECUTION="$LAST_TRADE_EXECUTION"
EOF
}

# Configuration management - Separate from runtime state
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE"
    fi
    
    # Set defaults if not configured
    STARTING_CASH=${STARTING_CASH:-25000}
}

save_config() {
    cat > "$CONFIG_FILE" << EOF
# Autopilot Configuration
# This file persists user preferences across restarts

STARTING_CASH="$STARTING_CASH"
EOF
}

validate_cash_amount() {
    local amount="$1"
    
    if [[ ! "$amount" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        error "Invalid cash amount: '$amount'. Must be a positive number."
        return 1
    fi
    
    if (( $(echo "$amount < 100" | bc -l 2>/dev/null || echo 1) )); then
        error "Cash amount too small: \$$(printf "%'.2f" "$amount"). Minimum is \$100."
        return 1
    fi
    
    if (( $(echo "$amount > 10000000" | bc -l 2>/dev/null || echo 0) )); then
        error "Cash amount too large: \$$(printf "%'.2f" "$amount"). Maximum is \$10M."
        return 1
    fi
    
    return 0
}

# Market day detection - Don't trade on weekends like an idiot
is_trading_day() {
    local day_of_week
    day_of_week=$(date +%u)  # 1=Monday, 7=Sunday
    
    # Weekend check
    if [[ "$day_of_week" -eq 6 || "$day_of_week" -eq 7 ]]; then
        return 1
    fi
    
    # TODO: Add holiday detection if you're feeling fancy
    return 0
}

# Convert to ET - Because markets don't care about your timezone
get_et_time() {
    TZ='America/New_York' date '+%H:%M'
}

get_et_date() {
    TZ='America/New_York' date '+%Y-%m-%d'
}

# Web monitor management - Keep that dashboard alive
start_web_monitor() {
    if [[ ! -d "$WEB_DIR" ]]; then
        error "Web monitor directory not found: $WEB_DIR"
        return 1
    fi
    
    info "Starting web monitor..."
    trace "Web monitor directory: $WEB_DIR"
    trace "Python executable: $VENV_DIR/bin/python"
    trace "Log file: $LOG_FILE.web"
    
    cd "$WEB_DIR"
    
    # Start in background and capture PID with unbuffered output
    "$VENV_DIR/bin/python" -u app.py > "$LOG_FILE.web" 2>&1 &
    local pid=$!
    
    trace "Web monitor started with PID: $pid"
    
    # Give it a moment to start
    sleep 2
    
    if kill -0 "$pid" 2>/dev/null; then
        echo "$pid" > "$WEB_MONITOR_PID_FILE"
        info "Web monitor started (PID: $pid)"
        # One-time probe to log Client Portal connection status for the dashboard
        if [[ -d "$IB_DIR" ]]; then
            info "Probing Client Portal connection..."
            trace "IB directory: $IB_DIR"
            (
                cd "$IB_DIR"
                run_cmd "$VENV_DIR/bin/python -u cp_executor.py --check-connection" || true
            ) &
        fi
        cd "$SCRIPT_DIR"
        return 0
    else
        error "Failed to start web monitor"
        cd "$SCRIPT_DIR"
        return 1
    fi
}

check_web_monitor() {
    local pid=""
    
    if [[ -f "$WEB_MONITOR_PID_FILE" ]]; then
        pid=$(cat "$WEB_MONITOR_PID_FILE" 2>/dev/null || echo "")
    fi
    
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        return 0  # Running
    else
        debug "Web monitor not running, restarting..."
        rm -f "$WEB_MONITOR_PID_FILE"
        start_web_monitor
    fi
}

# Daily portfolio update - The bread and butter
run_daily_update() {
    local today
    today=$(get_et_date)
    
    if [[ "$LAST_DAILY_UPDATE" == "$today" ]]; then
        debug "Daily update already completed today ($today)"
        return 0
    fi
    
    info "Running daily portfolio update..."
    trace "Portfolio file: $PORTFOLIO_FILE"
    trace "Trading script: $SCRIPT_DIR/trading_script.py"
    
    # Don't require portfolio file to exist - trading_script.py will create it if missing
    if [[ ! -f "$PORTFOLIO_FILE" ]]; then
        info "Portfolio file not found - will create new portfolio"
    fi
    
    if [[ ! -f "$SCRIPT_DIR/trading_script.py" ]]; then
        error "Trading script not found: $SCRIPT_DIR/trading_script.py"
        return 1
    fi
    
    # Load configuration to get starting cash
    load_config
    
    # Build command with starting cash
    local cmd="$VENV_DIR/bin/python -u \"$SCRIPT_DIR/trading_script.py\" --file \"$PORTFOLIO_FILE\" --no-interactive --starting-cash $STARTING_CASH"
    
    if ! run_cmd "$cmd"; then
        error "Daily update failed - check output above for details"
        return 1
    fi
    
    LAST_DAILY_UPDATE="$today"
    save_state
    info "Daily update completed successfully"
}

# Trade execution - Where the rubber meets the road
execute_pending_trades() {
    local today
    today=$(get_et_date)
    
    if [[ "$LAST_TRADE_EXECUTION" == "$today" ]]; then
        debug "Trade execution already completed today ($today)"
        return 0
    fi
    
    if [[ ! -d "$IB_DIR" ]]; then
        error "IB trading directory not found: $IB_DIR"
        return 1
    fi
    
    info "Executing pending trades..."
    trace "IB directory: $IB_DIR"
    trace "Switching to IB directory"
    cd "$IB_DIR"
    
    # First check what we have pending with full error capture
    local pending_count
    trace "Checking for pending trades with dry run"
    
    local dry_run_output
    if dry_run_output=$(run_cmd "$VENV_DIR/bin/python -u cp_executor.py --dry-run --show-trades" 2>&1); then
        pending_count=$(echo "$dry_run_output" | grep -c "^BUY\|^SELL" || echo "0")
        trace "Dry run output: $dry_run_output"
    else
        error "Failed to check pending trades - dry run failed"
        pending_count=0
    fi
    
    if [[ "$pending_count" -eq 0 ]]; then
        info "No pending trades to execute"
        cd "$SCRIPT_DIR"
        return 0
    fi
    
    info "Found $pending_count pending trades"
    trace "Executing trades for date: $today"
    
    # Execute the trades with full error capture
    if run_cmd "$VENV_DIR/bin/python -u cp_executor.py --execute-pending --date \"$today\" --no-confirm"; then
        LAST_TRADE_EXECUTION="$today"
        save_state
        info "Trade execution completed successfully"
    else
        error "Trade execution failed - check output above for details"
        cd "$SCRIPT_DIR"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
}

# Control file handlers - Simple IPC for simple minds
check_control_files() {
    # Pause trading operations
    if [[ -f ".autopilot.pause" ]]; then
        info "Pause file detected, skipping trading operations"
        return 1
    fi
    
    # Graceful shutdown
    if [[ -f ".autopilot.stop" ]]; then
        info "Stop file detected, shutting down"
        rm -f ".autopilot.stop"
        cleanup
    fi
    
    # Force update
    if [[ -f ".autopilot.force_update" ]]; then
        info "Force update requested"
        rm -f ".autopilot.force_update"
        LAST_DAILY_UPDATE=""  # Reset to force update
        run_daily_update
    fi
    
    # Skip next execution
    if [[ -f ".autopilot.skip_next" ]]; then
        info "Skip next execution requested"
        rm -f ".autopilot.skip_next"
        return 1
    fi
    
    return 0
}

# Fresh start - Wipe all state for clean pipeline run
fresh_start() {
    local starting_cash="${1:-}"
    
    # Load current config to get defaults
    load_config
    
    # Use provided amount or current config
    if [[ -n "$starting_cash" ]]; then
        if ! validate_cash_amount "$starting_cash"; then
            return 1
        fi
        STARTING_CASH="$starting_cash"
    fi
    echo "=== FRESH START - RESET ALL PIPELINE STATE ==="
    echo ""
    echo "This will DELETE:"
    echo "  • Autopilot state files (.autopilot.*)"
    echo "  • Checkpoint files (tracking processed trades)"
    echo "  • Execution logs (completed trade records)"
    echo "  • System logs (debug/error logs)"
    echo ""
    echo "This will BACKUP & RESET:"
    echo "  • CSV data files (portfolio/trades) - moved to .backup/"
    echo ""
    echo "This will PRESERVE:"
    echo "  • Configuration files"
    echo "  • Python scripts"
    echo ""
    
    # Require explicit confirmation
    read -p "Are you SURE you want a fresh start? Type 'yes' to confirm: " confirmation
    
    if [[ "$confirmation" != "yes" ]]; then
        echo "Aborted. Nothing was deleted."
        exit 0
    fi
    
    echo ""
    echo "Cleaning state files..."
    
    # Stop any running autopilot first
    if [[ -f "$LOCK_FILE" ]]; then
        local pid
        pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "Stopping running autopilot (PID: $pid)..."
            kill -TERM "$pid" 2>/dev/null || true
            sleep 2
        fi
    fi
    
    # Clean autopilot state files
    rm -fv "$STATE_FILE"
    rm -fv "$LOCK_FILE"
    rm -fv "$WEB_MONITOR_PID_FILE"
    rm -fv "$LOG_FILE"
    rm -fv "$LOG_FILE.web"
    
    # Clean control files
    rm -fv .autopilot.pause
    rm -fv .autopilot.stop
    rm -fv .autopilot.force_update
    rm -fv .autopilot.skip_next
    
    # Clean IB trading state
    echo "Cleaning IB trading state..."
    rm -fv "$IB_DIR/.ib_checkpoint.json"
    rm -fv "$IB_DIR/.cp_checkpoint.json"
    rm -fv "$IB_DIR"/*_checkpoint*.json
    
    # Clean execution logs
    rm -fv "$IB_DIR/cp_execution_log.csv"
    rm -fv "$IB_DIR/ib_execution_log.csv"
    rm -fv "$IB_DIR/test_executions.csv"
    
    # Clean API logs
    rm -fv "$IB_DIR/cp_api.log"
    rm -fv "$IB_DIR/ib_executor.log"
    rm -fv "$IB_DIR"/*.log
    
    # Backup and reset CSV data files for true fresh start
    echo "Backing up and resetting CSV data files..."
    BACKUP_DIR="$SCRIPT_DIR/.backup/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup portfolio CSV if it exists
    if [[ -f "$PORTFOLIO_FILE" ]]; then
        mv "$PORTFOLIO_FILE" "$BACKUP_DIR/"
        echo "  ✓ Backed up portfolio CSV to $BACKUP_DIR/"
    fi
    
    # Backup trade log CSV - check multiple possible locations
    TRADE_LOG="$SCRIPT_DIR/chatgpt_trade_log.csv"
    if [[ -f "$TRADE_LOG" ]]; then
        mv "$TRADE_LOG" "$BACKUP_DIR/"
        echo "  ✓ Backed up trade log CSV to $BACKUP_DIR/"
    fi
    
    # Also check in Scripts and CSV Files directory
    ALT_TRADE_LOG="$(dirname "$PORTFOLIO_FILE")/chatgpt_trade_log.csv"
    if [[ -f "$ALT_TRADE_LOG" ]]; then
        mv "$ALT_TRADE_LOG" "$BACKUP_DIR/"
        echo "  ✓ Backed up trade log CSV from $(dirname "$PORTFOLIO_FILE")/"
    fi
    
    # Save the configuration (not runtime state)
    save_config
    
    echo ""
    echo "✓ Fresh start complete - all state cleared and CSV files backed up"
    echo ""
    echo "Pipeline Configuration:"
    echo "  Starting cash: \$$(printf "%'.2f" "$STARTING_CASH")"
    echo ""
    echo "You can now start the autopilot with:"
    echo "  ./autopilot.sh start"
    echo ""
    echo "The pipeline will start with an empty portfolio and process trades from the beginning."
    if [[ -d "$BACKUP_DIR" ]]; then
        echo "Your previous data is safely backed up in: $BACKUP_DIR"
    fi
}

# Main event loop - Where the magic happens
main_loop() {
    info "Starting autopilot main loop"
    show_next_action
    
    local loop_count=0
    
    while true; do
        loop_count=$((loop_count + 1))
        
        # Check control files every iteration
        if ! check_control_files; then
            sleep 60
            continue
        fi
        
        local current_time
        current_time=$(get_et_time)
        
        # Ensure web monitor is running
        if ! check_web_monitor; then
            error "Web monitor health check failed"
        fi
        
        # Time-based execution
        case "$current_time" in
            "$DAILY_UPDATE_TIME")
                if is_trading_day; then
                    info "Triggering daily update (ET: $current_time)"
                    run_daily_update || error "Daily update failed"
                else
                    debug "Skipping daily update - not a trading day"
                    trace "Next trading day actions will resume Monday"
                fi
                ;;
            "$EXECUTE_TRADES_TIME")
                if is_trading_day; then
                    info "Triggering trade execution (ET: $current_time)"
                    execute_pending_trades || error "Trade execution failed"
                else
                    debug "Skipping trade execution - not a trading day"
                    trace "Next trading day actions will resume Monday"
                fi
                ;;
        esac
        
        # Health check every 100 loops (about 1.5 hours)
        if (( loop_count % 100 == 0 )); then
            info "Health check - Loop: $loop_count, ET: $current_time"
            show_next_action
            trace "Current working directory: $(pwd)"
            trace "Free disk space: $(df -h . | tail -1 | awk '{print $4}')"
            trace "Memory usage: $(free -h | grep Mem: | awk '{print $3"/"$2}')"
            
            # Check if CSV files are fresh
            if [[ -f "$PORTFOLIO_FILE" ]]; then
                local file_age file_mtime
                file_mtime=$(stat -c %Y "$PORTFOLIO_FILE")
                file_age=$(( $(date +%s) - file_mtime ))
                trace "Portfolio file: $PORTFOLIO_FILE"
                trace "File modified: $(date -d @$file_mtime)"
                trace "File age: $file_age seconds ($(( file_age / 3600 )) hours)"
                
                if (( file_age > 86400 )); then  # 24 hours
                    error "Portfolio file is stale ($(( file_age / 3600 )) hours old, last modified: $(date -d @$file_mtime))"
                fi
            else
                error "Portfolio file not found: $PORTFOLIO_FILE"
            fi
            
            # Check web monitor health
            trace "Checking web monitor health..."
            if [[ -f "$WEB_MONITOR_PID_FILE" ]]; then
                local web_pid
                web_pid=$(cat "$WEB_MONITOR_PID_FILE" 2>/dev/null || echo "")
                if [[ -n "$web_pid" ]] && kill -0 "$web_pid" 2>/dev/null; then
                    trace "Web monitor healthy (PID: $web_pid)"
                else
                    trace "Web monitor not running or unhealthy"
                fi
            fi
        fi
        
        # Sleep for 1 minute
        sleep 60
    done
}

# Usage information - Because RTFM doesn't work if there's no manual
# System diagnostics - Show everything that could be wrong
diagnose_system() {
    echo "=== AUTOPILOT SYSTEM DIAGNOSTICS ==="
    echo ""
    echo "Environment:"
    echo "  Script directory: $SCRIPT_DIR"
    echo "  Current user: $(whoami)"
    echo "  Current directory: $(pwd)"
    echo "  Python executable: $VENV_DIR/bin/python"
    echo "  Python version: $($VENV_DIR/bin/python --version 2>&1 || echo 'FAILED')"
    echo ""
    
    echo "Files and Directories:"
    for file in "$PORTFOLIO_FILE" "$SCRIPT_DIR/trading_script.py" "$IB_DIR" "$WEB_DIR"; do
        if [[ -e "$file" ]]; then
            if [[ -f "$file" ]]; then
                echo "  ✓ FILE: $file (size: $(stat -c%s "$file"), modified: $(stat -c%y "$file"))"
            elif [[ -d "$file" ]]; then
                echo "  ✓ DIR:  $file ($(ls -1 "$file" | wc -l) files)"
            fi
        else
            echo "  ✗ MISSING: $file"
        fi
    done
    echo ""
    
    echo "System Resources:"
    echo "  Memory: $(free -h | grep Mem: | awk '{print $3"/"$2" ("$4" free)"}')"
    echo "  Disk space: $(df -h . | tail -1 | awk '{print $3"/"$2" ("$4" available)"}')"
    echo "  Load average: $(uptime | awk -F'load average:' '{print $2}')"
    echo ""
    
    echo "Network Connectivity:"
    echo -n "  Internet: "
    if curl -s --connect-timeout 5 https://www.google.com >/dev/null; then
        echo "✓ Connected"
    else
        echo "✗ Failed"
    fi
    
    echo -n "  Client Portal (localhost:5000): "
    if curl -s --connect-timeout 5 http://localhost:5000/v1/api/portfolio/accounts >/dev/null 2>&1; then
        echo "✓ Accessible"
    else
        echo "✗ Not accessible"
    fi
    echo ""
    
    echo "Process Status:"
    if [[ -f "$LOCK_FILE" ]]; then
        local pid
        pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "  Autopilot: ✓ Running (PID: $pid)"
        else
            echo "  Autopilot: ✗ Stale lock file"
        fi
    else
        echo "  Autopilot: ✗ Not running"
    fi
    
    if [[ -f "$WEB_MONITOR_PID_FILE" ]]; then
        local web_pid
        web_pid=$(cat "$WEB_MONITOR_PID_FILE" 2>/dev/null || echo "")
        if [[ -n "$web_pid" ]] && kill -0 "$web_pid" 2>/dev/null; then
            echo "  Web Monitor: ✓ Running (PID: $web_pid)"
        else
            echo "  Web Monitor: ✗ Stale PID file"
        fi
    else
        echo "  Web Monitor: ✗ Not running"
    fi
    echo ""
    
    echo "Recent Errors (last 10 lines):"
    if [[ -f "$LOG_FILE" ]]; then
        grep -i error "$LOG_FILE" | tail -10 | sed 's/^/  /'
    else
        echo "  No log file found"
    fi
    echo ""
    
    echo "Python Packages:"
    echo -n "  Testing trading_script.py import: "
    if cd "$SCRIPT_DIR" && "$VENV_DIR/bin/python" -c "import trading_script" 2>/dev/null; then
        echo "✓ OK"
    else
        echo "✗ Failed"
    fi
    
    if [[ -d "$IB_DIR" ]]; then
        echo -n "  Testing cp_executor.py import: "
        if cd "$IB_DIR" && "$VENV_DIR/bin/python" -c "import cp_executor" 2>/dev/null; then
            echo "✓ OK"
        else
            echo "✗ Failed"
        fi
    fi
    
    cd "$SCRIPT_DIR"
    echo ""
    echo "For verbose output during operation, run: VERBOSE=1 ./autopilot.sh start"
}

usage() {
    cat << EOF
Usage: $0 [COMMAND]

Commands:
    start       Start the autopilot (default)
    stop        Stop running autopilot
    status      Show autopilot status
    fresh [AMT] Fresh start - clear all state files (optional: starting cash amount)
    pause       Pause trading operations
    resume      Resume trading operations
    force       Force daily update now
    skip        Skip next scheduled execution
    logs        Show recent log entries
    diagnose    Run system diagnostics

Verbose Mode:
    VERBOSE=1 ./autopilot.sh start    - Show all command output in real-time

Control files (create these to control running autopilot):
    .autopilot.pause        - Pause trading operations
    .autopilot.stop         - Graceful shutdown
    .autopilot.force_update - Force immediate update
    .autopilot.skip_next    - Skip next execution

EOF
}

# Command handling - Because this isn't just a daemon
case "${1:-start}" in
    "start")
        acquire_lock
        load_state
        load_config
        
        # Log autopilot startup to structured logs
        autopilot_exec_id=$(pipeline_log_startup "autopilot.sh" "{\"mode\": \"daemon\", \"pid\": $$, \"portfolio\": \"$PORTFOLIO_FILE\", \"daily_time\": \"$DAILY_UPDATE_TIME\", \"execute_time\": \"$EXECUTE_TRADES_TIME\"}")
        [[ -n "$autopilot_exec_id" ]] && pipeline_log_exec_start "$autopilot_exec_id"
        
        info "=== ChatGPT Trading Autopilot Starting ==="
        info "Portfolio: $PORTFOLIO_FILE"
        info "Daily update time: $DAILY_UPDATE_TIME ET"
        info "Trade execution time: $EXECUTE_TRADES_TIME ET"
        main_loop
        ;;
    "stop")
        if [[ -f "$LOCK_FILE" ]]; then
            pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
            if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
                echo "Stopping autopilot (PID: $pid)"
                kill -TERM "$pid"
                echo "Stop signal sent"
            else
                echo "Autopilot not running"
                rm -f "$LOCK_FILE"
            fi
        else
            echo "Autopilot not running"
        fi
        ;;
    "status")
        if [[ -f "$LOCK_FILE" ]]; then
            pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
            if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
                echo "Autopilot running (PID: $pid)"
                echo "Current time: $(get_et_time) ET ($(get_et_date))"
                show_next_action
                if [[ -f "$STATE_FILE" ]]; then
                    echo "State:"
                    cat "$STATE_FILE"
                fi
            else
                echo "Autopilot not running (stale lock file)"
            fi
        else
            echo "Autopilot not running"
            echo "Next scheduled actions when started:"
            echo "  Daily Update: $DAILY_UPDATE_TIME ET"
            echo "  Trade Execution: $EXECUTE_TRADES_TIME ET"
        fi
        ;;
    "fresh")
        fresh_start "$2"  # Pass second argument as starting cash
        ;;
    "pause")
        touch ".autopilot.pause"
        echo "Trading operations paused"
        ;;
    "resume")
        rm -f ".autopilot.pause"
        echo "Trading operations resumed"
        ;;
    "force")
        touch ".autopilot.force_update"
        echo "Forced update requested"
        ;;
    "skip")
        touch ".autopilot.skip_next"
        echo "Next execution will be skipped"
        ;;
    "logs")
        echo "=== PIPELINE LOG FILES ==="
        echo "Shell Log (Plain Text):"
        echo "  File: $LOG_FILE"
        if [[ -f "$LOG_FILE" ]]; then
            echo "  Size: $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) bytes"
            echo "  Modified: $(stat -c%y "$LOG_FILE" 2>/dev/null || echo 'N/A')"
        else
            echo "  Status: NOT FOUND"
        fi
        echo
        
        echo "Structured Logs (JSON):"
        pipeline_report_logs | while IFS='=' read -r key value; do
            case "$key" in
                "ACTIONS_LOG"|"EXECUTIONS_LOG"|"ERRORS_LOG")
                    echo "  $key: $value"
                    if [[ -f "$value" ]]; then
                        size=$(stat -c%s "$value" 2>/dev/null || echo 0)
                        modified=$(stat -c%y "$value" 2>/dev/null || echo 'N/A')
                        echo "    Size: ${size} bytes"
                        echo "    Modified: $modified"
                    else
                        echo "    Status: NOT FOUND"
                    fi
                    ;;
                "LOG_DIR")
                    echo "  Directory: $value"
                    ;;
                *"_SIZE")
                    # Size already handled above, skip
                    ;;
            esac
        done
        echo
        
        echo "Recent Shell Log Entries (last 20):"
        if [[ -f "$LOG_FILE" ]]; then
            tail -n 20 "$LOG_FILE"
        else
            echo "  No shell log file found"
        fi
        ;;
    "diagnose")
        diagnose_system
        ;;
    *)
        usage
        exit 1
        ;;
esac
