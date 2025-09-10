#!/usr/bin/env python3
"""
Unified Pipeline Action Logger

Production-ready structured logging system for the trading pipeline.
Implements proposals 1,2,3,5 from the documentation analysis.

Features:
- Unified action logging across all pipeline components
- Execution tracking with detailed evidence
- Audit report generation with daily summaries  
- Structured action categories (no magic strings)
- JSON output for production, pretty-print for development
- Exception tracking with structured tracebacks
- Performance metrics and timing data
"""

import json
import logging
import logging.config
import os
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union
import structlog


# Configuration Constants (no magic numbers)
DEFAULT_LOG_LEVEL = "INFO"
MAX_LOG_FILE_SIZE_MB = 100
LOG_RETENTION_DAYS = 30
AUDIT_REPORT_BATCH_SIZE = 1000


class ActionCategory(Enum):
    """Structured action categories for pipeline events."""
    STARTUP = "STARTUP"
    SHUTDOWN = "SHUTDOWN"
    CONFIG_LOAD = "CONFIG_LOAD"
    CONFIG_SAVE = "CONFIG_SAVE"
    PORTFOLIO_LOAD = "PORTFOLIO_LOAD"
    PORTFOLIO_SAVE = "PORTFOLIO_SAVE"
    PORTFOLIO_UPDATE = "PORTFOLIO_UPDATE"
    TRADE_SIGNAL = "TRADE_SIGNAL"
    TRADE_EXECUTION = "TRADE_EXECUTION"
    TRADE_COMPLETE = "TRADE_COMPLETE"
    TRADE_FAILED = "TRADE_FAILED"
    IB_CONNECT = "IB_CONNECT"
    IB_DISCONNECT = "IB_DISCONNECT"
    IB_AUTH = "IB_AUTH"
    DATA_FETCH = "DATA_FETCH"
    ERROR = "ERROR"
    VALIDATION = "VALIDATION"
    CHECKPOINT = "CHECKPOINT"
    AUDIT = "AUDIT"
    WEB_MONITOR = "WEB_MONITOR"


class PipelineLogger:
    """
    Unified pipeline action logger with structured output.
    
    Provides:
    - Consistent logging across all pipeline components
    - Execution tracking with timing and evidence
    - Structured exception handling
    - Development vs production output formats
    - Audit trail generation
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        """Initialize the pipeline logger."""
        self.log_dir = Path(log_dir or "logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup log files
        self.action_log = self.log_dir / "pipeline_actions.jsonl"
        self.execution_log = self.log_dir / "execution_tracking.jsonl"
        self.error_log = self.log_dir / "pipeline_errors.jsonl"
        
        # Configure structured logging
        self._configure_logging()
        
        # Get loggers
        self.logger = structlog.get_logger("pipeline")
        self.execution_logger = structlog.get_logger("execution")
        self.error_logger = structlog.get_logger("error")
        
    def _configure_logging(self):
        """Configure structlog with production-ready settings."""
        
        # Determine output format based on environment
        is_development = sys.stderr.isatty()
        
        # Shared processors for all loggers
        shared_processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.CallsiteParameterAdder({
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }),
        ]
        
        if is_development:
            # Pretty printing for development
            processors = shared_processors + [
                structlog.dev.ConsoleRenderer(colors=True),
            ]
        else:
            # JSON output for production
            processors = shared_processors + [
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ]
        
        # Configure structlog
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        # Configure standard library logging for file output
        logging.basicConfig(
            format="%(message)s",
            level=getattr(logging, DEFAULT_LOG_LEVEL),
            handlers=[
                logging.FileHandler(self.action_log, mode='a'),
                logging.StreamHandler(sys.stdout),
            ]
        )
    
    def log_action(
        self,
        category: ActionCategory,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Log a pipeline action with structured data.
        
        Args:
            category: Action category from ActionCategory enum
            action: Specific action description
            details: Additional structured data
            execution_id: Optional execution tracking ID
            **kwargs: Additional key-value pairs
        
        Returns:
            Generated execution ID for tracking
        """
        if execution_id is None:
            execution_id = self._generate_execution_id()
        
        log_data = {
            "category": category.value,
            "action": action,
            "execution_id": execution_id,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {},
            **kwargs
        }
        
        self.logger.info("Pipeline action", **log_data)
        
        # Write to action log file
        self._write_to_file(self.action_log, log_data)
        
        return execution_id
    
    def log_execution(
        self,
        execution_id: str,
        status: str,
        duration_ms: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        **kwargs
    ):
        """
        Log execution tracking information.
        
        Args:
            execution_id: Execution ID from log_action
            status: Execution status (STARTED, COMPLETED, FAILED)
            duration_ms: Execution duration in milliseconds
            result: Execution result data
            error: Error message if failed
            **kwargs: Additional tracking data
        """
        log_data = {
            "execution_id": execution_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_ms": duration_ms,
            "result": result,
            "error": error,
            **kwargs
        }
        
        self.execution_logger.info("Execution update", **log_data)
        
        # Write to execution log file  
        self._write_to_file(self.execution_log, log_data)
    
    def log_error(
        self,
        category: ActionCategory,
        error_msg: str,
        exception: Optional[Exception] = None,
        execution_id: Optional[str] = None,
        **kwargs
    ):
        """
        Log pipeline errors with structured exception data.
        
        Args:
            category: Action category where error occurred
            error_msg: Error description
            exception: Python exception object
            execution_id: Related execution ID
            **kwargs: Additional error context
        """
        log_data = {
            "category": category.value,
            "error_msg": error_msg,
            "execution_id": execution_id,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        
        if exception:
            log_data["exception_type"] = type(exception).__name__
            log_data["exception_str"] = str(exception)
        
        self.error_logger.error("Pipeline error", **log_data, exc_info=exception is not None)
        
        # Write to error log file
        self._write_to_file(self.error_log, log_data)
    
    def generate_audit_report(
        self, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive audit report from pipeline logs.
        
        Args:
            start_date: Start date in ISO format (default: today)
            end_date: End date in ISO format (default: today)
            
        Returns:
            Structured audit report with statistics and summaries
        """
        if start_date is None:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if end_date is None:
            end_date = start_date
        
        report = {
            "report_generated": datetime.utcnow().isoformat(),
            "period_start": start_date,
            "period_end": end_date,
            "summary": {
                "total_actions": 0,
                "actions_by_category": {},
                "total_executions": 0,
                "execution_stats": {
                    "completed": 0,
                    "failed": 0,
                    "avg_duration_ms": 0
                },
                "total_errors": 0,
                "errors_by_category": {}
            },
            "details": {
                "actions": [],
                "executions": [],
                "errors": []
            }
        }
        
        # Process action logs
        actions = self._read_log_entries(self.action_log, start_date, end_date)
        report["summary"]["total_actions"] = len(actions)
        report["details"]["actions"] = actions
        
        for action in actions:
            category = action.get("category", "UNKNOWN")
            report["summary"]["actions_by_category"][category] = \
                report["summary"]["actions_by_category"].get(category, 0) + 1
        
        # Process execution logs
        executions = self._read_log_entries(self.execution_log, start_date, end_date)
        report["summary"]["total_executions"] = len(executions)
        report["details"]["executions"] = executions
        
        completed_durations = []
        for execution in executions:
            status = execution.get("status", "UNKNOWN")
            if status == "COMPLETED":
                report["summary"]["execution_stats"]["completed"] += 1
                duration = execution.get("duration_ms")
                if duration:
                    completed_durations.append(duration)
            elif status == "FAILED":
                report["summary"]["execution_stats"]["failed"] += 1
        
        if completed_durations:
            report["summary"]["execution_stats"]["avg_duration_ms"] = \
                sum(completed_durations) / len(completed_durations)
        
        # Process error logs
        errors = self._read_log_entries(self.error_log, start_date, end_date)
        report["summary"]["total_errors"] = len(errors)
        report["details"]["errors"] = errors
        
        for error in errors:
            category = error.get("category", "UNKNOWN")
            report["summary"]["errors_by_category"][category] = \
                report["summary"]["errors_by_category"].get(category, 0) + 1
        
        # Save report
        report_file = self.log_dir / f"audit_report_{start_date}_{end_date}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        return f"exec_{timestamp}"
    
    def _write_to_file(self, filepath: Path, data: Dict[str, Any]):
        """Write log entry to JSONL file."""
        try:
            with open(filepath, 'a') as f:
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            # Fallback logging if file write fails
            print(f"Failed to write to {filepath}: {e}", file=sys.stderr)
    
    def _read_log_entries(
        self, 
        filepath: Path, 
        start_date: str, 
        end_date: str
    ) -> list[Dict[str, Any]]:
        """Read and filter log entries by date range."""
        entries = []
        
        if not filepath.exists():
            return entries
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_date = entry.get("timestamp", "")[:10]  # Extract YYYY-MM-DD
                        
                        if start_date <= entry_date <= end_date:
                            entries.append(entry)
                            
                        # Limit batch size to prevent memory issues
                        if len(entries) >= AUDIT_REPORT_BATCH_SIZE:
                            break
                            
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            print(f"Error reading {filepath}: {e}", file=sys.stderr)
        
        return entries


# Global logger instance
_pipeline_logger: Optional[PipelineLogger] = None


def get_pipeline_logger(log_dir: Optional[str] = None) -> PipelineLogger:
    """Get or create global pipeline logger instance."""
    global _pipeline_logger
    
    if _pipeline_logger is None:
        _pipeline_logger = PipelineLogger(log_dir)
    
    return _pipeline_logger


# Convenience functions for common logging patterns
def log_startup(component: str, details: Optional[Dict[str, Any]] = None) -> str:
    """Log component startup."""
    return get_pipeline_logger().log_action(
        ActionCategory.STARTUP,
        f"{component} starting up",
        details
    )


def log_trade_signal(ticker: str, action: str, details: Optional[Dict[str, Any]] = None) -> str:
    """Log trade signal generation."""
    return get_pipeline_logger().log_action(
        ActionCategory.TRADE_SIGNAL,
        f"Trade signal: {action} {ticker}",
        details
    )


def log_portfolio_update(details: Optional[Dict[str, Any]] = None) -> str:
    """Log portfolio update."""
    return get_pipeline_logger().log_action(
        ActionCategory.PORTFOLIO_UPDATE,
        "Portfolio updated",
        details
    )


def log_execution_start(execution_id: str):
    """Log execution start."""
    get_pipeline_logger().log_execution(execution_id, "STARTED")


def log_execution_complete(execution_id: str, duration_ms: float, result: Optional[Dict[str, Any]] = None):
    """Log execution completion."""
    get_pipeline_logger().log_execution(execution_id, "COMPLETED", duration_ms, result)


def log_execution_failed(execution_id: str, duration_ms: float, error: str):
    """Log execution failure."""
    get_pipeline_logger().log_execution(execution_id, "FAILED", duration_ms, error=error)


def log_pipeline_error(category: ActionCategory, error_msg: str, exception: Optional[Exception] = None, **kwargs):
    """Log pipeline error."""
    get_pipeline_logger().log_error(category, error_msg, exception, **kwargs)


if __name__ == "__main__":
    # Test the logging system
    logger = get_pipeline_logger("test_logs")
    
    # Test basic logging
    exec_id = log_startup("trading_script", {"version": "1.0", "mode": "test"})
    log_execution_start(exec_id)
    log_execution_complete(exec_id, 150.5, {"status": "success"})
    
    # Test trade logging
    trade_id = log_trade_signal("AAPL", "BUY", {"price": 150.0, "shares": 100})
    log_execution_start(trade_id)
    log_execution_complete(trade_id, 250.2, {"executed_price": 150.1})
    
    # Test error logging
    try:
        raise ValueError("Test error for logging")
    except ValueError as e:
        log_pipeline_error(ActionCategory.ERROR, "Test error occurred", e)
    
    # Generate audit report
    report = logger.generate_audit_report()
    print(f"Generated audit report with {report['summary']['total_actions']} actions")