from __future__ import annotations

from typing import Any, Dict, Optional

try:
    # Prefer the project's structured logger if available
    from pipeline_logger import (
        get_pipeline_logger,
        log_startup as _log_startup,
        log_execution_start as _log_execution_start,
        log_execution_complete as _log_execution_complete,
        log_execution_failed as _log_execution_failed,
        log_pipeline_error as _log_pipeline_error,
        ActionCategory,
    )
    _HAS_PIPELINE = True
except Exception:  # pragma: no cover - fallback
    import logging
    _HAS_PIPELINE = False
    _stdlog = logging.getLogger("microcap")
    _stdlog.setLevel(logging.INFO)


def startup(component: str, details: Optional[Dict[str, Any]] = None) -> str:
    if _HAS_PIPELINE:
        return _log_startup(component, details)
    return "exec-0"


def exec_start(exec_id: str) -> None:
    if _HAS_PIPELINE:
        _log_execution_start(exec_id)


def exec_complete(exec_id: str, duration_ms: float, result: Optional[Dict[str, Any]] = None) -> None:
    if _HAS_PIPELINE:
        _log_execution_complete(exec_id, duration_ms, result)


def exec_failed(exec_id: str, duration_ms: float, error: str) -> None:
    if _HAS_PIPELINE:
        _log_execution_failed(exec_id, duration_ms, error)


def pipeline_error(message: str, exception: Optional[Exception] = None) -> None:
    if _HAS_PIPELINE:
        _log_pipeline_error(ActionCategory.ERROR, message, exception)

