#!/usr/bin/env python3
"""
Shell-to-Python Pipeline Logger Bridge

Command-line interface for autopilot.sh to log structured events.
Provides unified logging across shell and Python components.

Usage:
    ./shell_logger.py startup "autopilot.sh" '{"mode": "daemon", "pid": 1234}'
    ./shell_logger.py action PORTFOLIO_UPDATE "Daily portfolio sync" '{"cash": 1000}'
    ./shell_logger.py exec_start exec_123
    ./shell_logger.py exec_complete exec_123 1500 '{"success": true}'
    ./shell_logger.py exec_failed exec_123 2000 "Connection timeout"
    ./shell_logger.py error IB_CONNECT "Failed to authenticate" '{"host": "127.0.0.1"}'
    ./shell_logger.py report_logs

This ensures autopilot.sh events flow into the same structured logging system.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline_logger import (
    get_pipeline_logger, ActionCategory, 
    log_startup, log_execution_start, log_execution_complete, 
    log_execution_failed, log_pipeline_error
)


def parse_json_safely(json_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse JSON string safely, return None if invalid."""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"WARNING: Invalid JSON '{json_str}': {e}", file=sys.stderr)
        return None


def get_action_category(category_str: str) -> ActionCategory:
    """Convert string to ActionCategory enum safely."""
    try:
        return ActionCategory[category_str.upper()]
    except KeyError:
        print(f"WARNING: Unknown category '{category_str}', using ERROR", file=sys.stderr)
        return ActionCategory.ERROR


def cmd_startup(args):
    """Log component startup from shell."""
    component = args.component
    details = parse_json_safely(args.details)
    
    # Redirect structured log output to stderr to avoid capture by shell
    import sys
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    
    try:
        exec_id = log_startup(component, details)
    finally:
        sys.stdout = old_stdout
    
    print(exec_id)  # Return ONLY execution ID for shell to use
    return 0


def cmd_action(args):
    """Log pipeline action from shell."""
    logger = get_pipeline_logger()
    category = get_action_category(args.category)
    details = parse_json_safely(args.details)
    
    # Redirect structured log output to stderr to avoid capture by shell
    import sys
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    
    try:
        exec_id = logger.log_action(category, args.action, details)
    finally:
        sys.stdout = old_stdout
    
    print(exec_id)  # Return ONLY execution ID for shell to use
    return 0


def cmd_exec_start(args):
    """Log execution start from shell."""
    log_execution_start(args.exec_id)
    return 0


def cmd_exec_complete(args):
    """Log execution completion from shell."""
    result = parse_json_safely(args.result)
    log_execution_complete(args.exec_id, float(args.duration_ms), result)
    return 0


def cmd_exec_failed(args):
    """Log execution failure from shell."""
    log_execution_failed(args.exec_id, float(args.duration_ms), args.error)
    return 0


def cmd_error(args):
    """Log pipeline error from shell."""
    category = get_action_category(args.category)
    details = parse_json_safely(args.details)
    log_pipeline_error(category, args.message, None, **details or {})
    return 0


def cmd_report_logs(args):
    """Report the current log file locations."""
    logger = get_pipeline_logger()
    
    print("PIPELINE_LOG_FILES:")
    print(f"ACTIONS_LOG={logger.action_log}")
    print(f"EXECUTIONS_LOG={logger.execution_log}")
    print(f"ERRORS_LOG={logger.error_log}")
    print(f"LOG_DIR={logger.log_dir}")
    
    # Report file sizes
    for log_file in [logger.action_log, logger.execution_log, logger.error_log]:
        if log_file.exists():
            size_kb = log_file.stat().st_size / 1024
            print(f"{log_file.name}_SIZE={size_kb:.1f}KB")
        else:
            print(f"{log_file.name}_SIZE=0KB")
    
    return 0


def cmd_audit_report(args):
    """Generate and report audit summary."""
    logger = get_pipeline_logger()
    report = logger.generate_audit_report()
    
    print("PIPELINE_AUDIT_SUMMARY:")
    print(f"TOTAL_ACTIONS={report['summary']['total_actions']}")
    print(f"TOTAL_EXECUTIONS={report['summary']['total_executions']}")
    print(f"COMPLETED_EXECUTIONS={report['summary']['execution_stats']['completed']}")
    print(f"FAILED_EXECUTIONS={report['summary']['execution_stats']['failed']}")
    print(f"TOTAL_ERRORS={report['summary']['total_errors']}")
    print(f"AVG_DURATION_MS={report['summary']['execution_stats']['avg_duration_ms']:.2f}")
    
    # Print top categories
    actions_by_cat = report['summary']['actions_by_category']
    if actions_by_cat:
        top_category = max(actions_by_cat.items(), key=lambda x: x[1])
        print(f"TOP_ACTION_CATEGORY={top_category[0]}:{top_category[1]}")
    
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Shell-to-Python pipeline logger bridge",
        epilog="All events flow into unified structured logging system"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # startup command
    startup_parser = subparsers.add_parser('startup', help='Log component startup')
    startup_parser.add_argument('component', help='Component name (e.g., autopilot.sh)')
    startup_parser.add_argument('details', nargs='?', help='JSON details object')
    startup_parser.set_defaults(func=cmd_startup)
    
    # action command  
    action_parser = subparsers.add_parser('action', help='Log pipeline action')
    action_parser.add_argument('category', help='Action category (STARTUP, PORTFOLIO_UPDATE, etc.)')
    action_parser.add_argument('action', help='Action description')
    action_parser.add_argument('details', nargs='?', help='JSON details object')
    action_parser.set_defaults(func=cmd_action)
    
    # exec_start command
    exec_start_parser = subparsers.add_parser('exec_start', help='Log execution start')
    exec_start_parser.add_argument('exec_id', help='Execution ID')
    exec_start_parser.set_defaults(func=cmd_exec_start)
    
    # exec_complete command
    exec_complete_parser = subparsers.add_parser('exec_complete', help='Log execution completion')
    exec_complete_parser.add_argument('exec_id', help='Execution ID')
    exec_complete_parser.add_argument('duration_ms', help='Duration in milliseconds')
    exec_complete_parser.add_argument('result', nargs='?', help='JSON result object')
    exec_complete_parser.set_defaults(func=cmd_exec_complete)
    
    # exec_failed command
    exec_failed_parser = subparsers.add_parser('exec_failed', help='Log execution failure')
    exec_failed_parser.add_argument('exec_id', help='Execution ID')
    exec_failed_parser.add_argument('duration_ms', help='Duration in milliseconds')
    exec_failed_parser.add_argument('error', help='Error message')
    exec_failed_parser.set_defaults(func=cmd_exec_failed)
    
    # error command
    error_parser = subparsers.add_parser('error', help='Log pipeline error')
    error_parser.add_argument('category', help='Error category')
    error_parser.add_argument('message', help='Error message')
    error_parser.add_argument('details', nargs='?', help='JSON details object')
    error_parser.set_defaults(func=cmd_error)
    
    # report_logs command
    report_parser = subparsers.add_parser('report_logs', help='Report log file locations')
    report_parser.set_defaults(func=cmd_report_logs)
    
    # audit_report command
    audit_parser = subparsers.add_parser('audit_report', help='Generate audit summary')
    audit_parser.set_defaults(func=cmd_audit_report)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit(main())