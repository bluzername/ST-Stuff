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

# Configuration - Because hardcoding is for idiots
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/autopilot.log"
STATE_FILE="$SCRIPT_DIR/.autopilot.state"
LOCK_FILE="$SCRIPT_DIR/.autopilot.lock"
WEB_MONITOR_PID_FILE="$SCRIPT_DIR/.web_monitor.pid"

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
    cd "$WEB_DIR"
    
    # Start in background and capture PID
    python app.py > "$LOG_FILE.web" 2>&1 &
    local pid=$!
    
    # Give it a moment to start
    sleep 2
    
    if kill -0 "$pid" 2>/dev/null; then
        echo "$pid" > "$WEB_MONITOR_PID_FILE"
        info "Web monitor started (PID: $pid)"
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
    
    if ! python "$SCRIPT_DIR/trading_script.py" --file "$PORTFOLIO_FILE" >> "$LOG_FILE" 2>&1; then
        error "Daily update failed"
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
    cd "$IB_DIR"
    
    # First check what we have pending
    local pending_count
    if ! pending_count=$(python ib_executor.py --dry-run --show-trades 2>/dev/null | grep -c "^BUY\|^SELL" || echo "0"); then
        pending_count=0
    fi
    
    if [[ "$pending_count" -eq 0 ]]; then
        info "No pending trades to execute"
        cd "$SCRIPT_DIR"
        return 0
    fi
    
    info "Found $pending_count pending trades"
    
    # Execute the trades
    if python ib_executor.py --execute-pending --date "$today" --no-confirm >> "$LOG_FILE" 2>&1; then
        LAST_TRADE_EXECUTION="$today"
        save_state
        info "Trade execution completed successfully"
    else
        error "Trade execution failed"
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

# Main event loop - Where the magic happens
main_loop() {
    info "Starting autopilot main loop"
    
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
                fi
                ;;
            "$EXECUTE_TRADES_TIME")
                if is_trading_day; then
                    info "Triggering trade execution (ET: $current_time)"
                    execute_pending_trades || error "Trade execution failed"
                else
                    debug "Skipping trade execution - not a trading day"
                fi
                ;;
        esac
        
        # Health check every 100 loops (about 1.5 hours)
        if (( loop_count % 100 == 0 )); then
            info "Health check - Loop: $loop_count, ET: $current_time"
            
            # Check if CSV files are fresh
            if [[ -f "$PORTFOLIO_FILE" ]]; then
                local file_age
                file_age=$(( $(date +%s) - $(stat -c %Y "$PORTFOLIO_FILE") ))
                if (( file_age > 86400 )); then  # 24 hours
                    error "Portfolio file is stale ($(( file_age / 3600 )) hours old)"
                fi
            fi
        fi
        
        # Sleep for 1 minute
        sleep 60
    done
}

# Usage information - Because RTFM doesn't work if there's no manual
usage() {
    cat << EOF
Usage: $0 [COMMAND]

Commands:
    start       Start the autopilot (default)
    stop        Stop running autopilot
    status      Show autopilot status
    pause       Pause trading operations
    resume      Resume trading operations
    force       Force daily update now
    skip        Skip next scheduled execution
    logs        Show recent log entries

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
                if [[ -f "$STATE_FILE" ]]; then
                    echo "State:"
                    cat "$STATE_FILE"
                fi
            else
                echo "Autopilot not running (stale lock file)"
            fi
        else
            echo "Autopilot not running"
        fi
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
        if [[ -f "$LOG_FILE" ]]; then
            tail -n 50 "$LOG_FILE"
        else
            echo "No log file found"
        fi
        ;;
    *)
        usage
        exit 1
        ;;
esac