#!/usr/bin/env python3
"""
Status data structure and JSON schema for autopilot.sh TUI
Defines the complete status model for real-time terminal monitoring
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import json
import os


class ComponentStatus(Enum):
    """Component health status indicators"""
    HEALTHY = "healthy"
    WARNING = "warning" 
    ERROR = "error"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


class ActionStatus(Enum):
    """Status of scheduled actions"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ComponentHealth:
    """Health status for a system component"""
    name: str
    status: ComponentStatus
    last_check: str  # ISO timestamp
    message: str
    uptime_seconds: Optional[int] = None
    pid: Optional[int] = None
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None


@dataclass
class PortfolioMetrics:
    """Current portfolio state metrics"""
    total_equity: float
    cash_balance: float
    positions_count: int
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl_percent: float
    last_updated: str  # ISO timestamp
    market_session: str  # "pre-market", "regular", "after-hours", "closed"


@dataclass
class ScheduledAction:
    """Upcoming or recent scheduled action"""
    name: str
    next_run: str  # ISO timestamp
    last_run: Optional[str]  # ISO timestamp
    status: ActionStatus
    frequency: str  # "daily", "intraday", "on-demand"
    countdown_seconds: Optional[int] = None
    last_duration_ms: Optional[int] = None


@dataclass
class SystemMetrics:
    """System resource usage"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_average: List[float]  # 1min, 5min, 15min
    uptime_seconds: int
    python_processes: int
    
    
@dataclass
class LogEntry:
    """Recent log entry for display"""
    timestamp: str
    level: str
    component: str
    message: str
    execution_id: Optional[str] = None


@dataclass
class AutopilotStatus:
    """Complete autopilot system status"""
    timestamp: str  # ISO timestamp of this status snapshot
    components: List[ComponentHealth]
    portfolio: PortfolioMetrics
    scheduled_actions: List[ScheduledAction]
    system: SystemMetrics
    recent_logs: List[LogEntry]
    mode: str  # "daemon", "test", "manual"
    pid: int
    version: str = "1.0"


class StatusManager:
    """Manages status file operations and updates"""
    
    def __init__(self, status_file: str = "/tmp/autopilot_status.json"):
        self.status_file = status_file
        
    def create_default_status(self) -> AutopilotStatus:
        """Create default status structure"""
        now = datetime.now().isoformat()
        
        # Default component health
        components = [
            ComponentHealth(
                name="Trading Script",
                status=ComponentStatus.UNKNOWN,
                last_check=now,
                message="Not initialized"
            ),
            ComponentHealth(
                name="IB Connection", 
                status=ComponentStatus.UNKNOWN,
                last_check=now,
                message="Connection status unknown"
            ),
            ComponentHealth(
                name="Web Monitor",
                status=ComponentStatus.UNKNOWN, 
                last_check=now,
                message="Web server status unknown"
            ),
            ComponentHealth(
                name="Pipeline Logger",
                status=ComponentStatus.UNKNOWN,
                last_check=now, 
                message="Logger not initialized"
            )
        ]
        
        # Default portfolio metrics
        portfolio = PortfolioMetrics(
            total_equity=1000.0,
            cash_balance=1000.0,
            positions_count=0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            daily_pnl_percent=0.0,
            last_updated=now,
            market_session="closed"
        )
        
        # Default scheduled actions
        scheduled_actions = [
            ScheduledAction(
                name="Daily Portfolio Update",
                next_run=now,
                last_run=None,
                status=ActionStatus.PENDING,
                frequency="daily"
            ),
            ScheduledAction(
                name="Intraday Execution", 
                next_run=now,
                last_run=None,
                status=ActionStatus.PENDING,
                frequency="intraday"
            )
        ]
        
        # Default system metrics
        system = SystemMetrics(
            cpu_percent=0.0,
            memory_percent=0.0, 
            disk_percent=0.0,
            load_average=[0.0, 0.0, 0.0],
            uptime_seconds=0,
            python_processes=0
        )
        
        return AutopilotStatus(
            timestamp=now,
            components=components,
            portfolio=portfolio,
            scheduled_actions=scheduled_actions,
            system=system,
            recent_logs=[],
            mode="manual",
            pid=os.getpid()
        )
    
    def load_status(self) -> AutopilotStatus:
        """Load status from file or create default"""
        try:
            with open(self.status_file, 'r') as f:
                data = json.load(f)
                return self._dict_to_status(data)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return self.create_default_status()
    
    def save_status(self, status: AutopilotStatus) -> None:
        """Save status to file"""
        try:
            # Convert to dict and handle enums
            status_dict = asdict(status)
            self._convert_enums_to_strings(status_dict)

            # Atomic write: write to temp file, fsync, then replace
            directory = os.path.dirname(self.status_file) or "."
            tmp_path = f"{self.status_file}.tmp"
            with open(tmp_path, 'w') as f:
                json.dump(status_dict, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.status_file)
        except Exception as e:
            # Best-effort cleanup of temp file
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            print(f"Warning: Could not save status file atomically: {e}")
    
    def _convert_enums_to_strings(self, data: Any) -> None:
        """Recursively convert enums to strings for JSON serialization"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (ComponentStatus, ActionStatus)):
                    data[key] = value.value
                elif isinstance(value, (dict, list)):
                    self._convert_enums_to_strings(value)
        elif isinstance(data, list):
            for item in data:
                self._convert_enums_to_strings(item)
    
    def update_component_status(self, component_name: str, 
                              status: ComponentStatus, message: str,
                              **kwargs) -> None:
        """Update specific component status"""
        current_status = self.load_status()
        
        # Find and update component
        for component in current_status.components:
            if component.name == component_name:
                component.status = status
                component.message = message
                component.last_check = datetime.now().isoformat()
                for key, value in kwargs.items():
                    if hasattr(component, key):
                        setattr(component, key, value)
                break
        
        current_status.timestamp = datetime.now().isoformat()
        self.save_status(current_status)
    
    def update_portfolio_metrics(self, **metrics) -> None:
        """Update portfolio metrics"""
        current_status = self.load_status()
        
        for key, value in metrics.items():
            if hasattr(current_status.portfolio, key):
                setattr(current_status.portfolio, key, value)
        
        current_status.portfolio.last_updated = datetime.now().isoformat()
        current_status.timestamp = datetime.now().isoformat()
        self.save_status(current_status)
    
    def add_log_entry(self, level: str, component: str, message: str, 
                     execution_id: Optional[str] = None) -> None:
        """Add recent log entry"""
        current_status = self.load_status()
        
        log_entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            component=component,
            message=message,
            execution_id=execution_id
        )
        
        current_status.recent_logs.insert(0, log_entry)
        current_status.recent_logs = current_status.recent_logs[:50]  # Keep last 50
        current_status.timestamp = datetime.now().isoformat()
        self.save_status(current_status)
    
    def _dict_to_status(self, data: Dict[str, Any]) -> AutopilotStatus:
        """Convert dictionary back to AutopilotStatus object"""
        # Convert enum values back to enums
        for comp in data.get('components', []):
            comp['status'] = ComponentStatus(comp['status'])
        
        for action in data.get('scheduled_actions', []):
            action['status'] = ActionStatus(action['status'])
        
        # Reconstruct nested objects
        components = [ComponentHealth(**comp) for comp in data.get('components', [])]
        portfolio = PortfolioMetrics(**data.get('portfolio', {}))
        scheduled_actions = [ScheduledAction(**action) for action in data.get('scheduled_actions', [])]
        system = SystemMetrics(**data.get('system', {}))
        recent_logs = [LogEntry(**log) for log in data.get('recent_logs', [])]
        
        return AutopilotStatus(
            timestamp=data.get('timestamp', datetime.now().isoformat()),
            components=components,
            portfolio=portfolio,
            scheduled_actions=scheduled_actions,
            system=system,
            recent_logs=recent_logs,
            mode=data.get('mode', 'manual'),
            pid=data.get('pid', os.getpid()),
            version=data.get('version', '1.0')
        )


if __name__ == "__main__":
    # Demo usage
    manager = StatusManager()
    status = manager.create_default_status()
    manager.save_status(status)
    
    print("Created default status file at /tmp/autopilot_status.json")
    print(f"Status contains {len(status.components)} components")
    print(f"Portfolio equity: ${status.portfolio.total_equity}")
