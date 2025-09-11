#!/usr/bin/env python3
"""
Terminal User Interface Controller for autopilot.sh
Real-time dashboard with split regions showing system status
"""

import json
import time
import threading
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
from pathlib import Path
from typing import Optional, Dict, Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.rule import Rule
from rich.align import Align
from rich.box import ROUNDED, MINIMAL

from status_schema import StatusManager, AutopilotStatus, ComponentStatus, ActionStatus


class TUIController:
    """Rich-based terminal UI controller for autopilot status"""
    
    def __init__(self, status_file: str = "/tmp/autopilot_status.json", 
                 refresh_rate: int = 2):
        self.status_manager = StatusManager(status_file)
        self.refresh_rate = refresh_rate
        self.console = Console()
        self.running = False
        self.current_status: Optional[AutopilotStatus] = None
        self._last_error: Optional[str] = None
        
        # Color schemes
        self.status_colors = {
            ComponentStatus.HEALTHY: "bright_green",
            ComponentStatus.WARNING: "bright_yellow", 
            ComponentStatus.ERROR: "bright_red",
            ComponentStatus.UNKNOWN: "dim",
            ComponentStatus.DISABLED: "bright_black"
        }
        
        self.action_colors = {
            ActionStatus.PENDING: "bright_blue",
            ActionStatus.RUNNING: "bright_cyan",
            ActionStatus.COMPLETED: "bright_green",
            ActionStatus.FAILED: "bright_red",
            ActionStatus.SKIPPED: "dim"
        }
    
    def create_layout(self) -> Layout:
        """Create the main layout with split regions"""
        layout = Layout(name="root")
        
        # Split into main sections
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=7)
        )
        
        # Split body into left and right columns
        layout["body"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Split left column into status and metrics
        layout["left"].split_column(
            Layout(name="components", ratio=1),
            Layout(name="portfolio", size=8)
        )
        
        # Split right column into actions and system
        layout["right"].split_column(
            Layout(name="actions", ratio=1),
            Layout(name="system", size=10)
        )
        
        return layout
    
    def render_header(self) -> Panel:
        """Render header with title and timestamp"""
        if not self.current_status:
            return Panel("AutoPilot Status Dashboard - No Data", style="bold blue")
        
        title = Text("AutoPilot Trading System", style="bold bright_blue")
        timestamp = Text(f"Updated: {self.current_status.timestamp[:19]}", style="dim")
        mode = Text(f"Mode: {self.current_status.mode.upper()}", 
                   style="bold bright_green" if self.current_status.mode == "daemon" else "bold bright_yellow")
        pid = Text(f"PID: {self.current_status.pid}", style="dim")
        
        header_content = Columns([title, timestamp, mode, pid], align="left", expand=True)
        return Panel(header_content, style="blue", box=ROUNDED)
    
    def render_components(self) -> Panel:
        """Render component health status"""
        if not self.current_status:
            return Panel("No component data", title="Components", style="dim")
        
        table = Table(show_header=True, header_style="bold cyan", box=MINIMAL)
        table.add_column("Component", style="bright_white", width=15)
        table.add_column("Status", width=10)
        table.add_column("Message", style="dim", overflow="ellipsis")
        table.add_column("PID", width=6, style="dim")
        
        for component in self.current_status.components:
            # Status with colored indicator
            status_color = self.status_colors.get(component.status, "white")
            status_text = f"{'●' if component.status == ComponentStatus.HEALTHY else '●'} {component.status.value.upper()}"
            
            # PID display
            pid_display = str(component.pid) if component.pid else "-"
            
            table.add_row(
                component.name,
                Text(status_text, style=status_color),
                component.message,
                pid_display
            )
        
        return Panel(table, title="Component Health", style="cyan", box=ROUNDED)
    
    def render_portfolio(self) -> Panel:
        """Render portfolio metrics"""
        if not self.current_status:
            return Panel("No portfolio data", title="Portfolio", style="dim")
        
        portfolio = self.current_status.portfolio
        
        # Main metrics table
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="cyan", width=12)
        table.add_column("Value", style="bright_white", justify="right", width=12)
        table.add_column("Change", width=8)
        
        # Format values with colors
        equity_color = "bright_green" if portfolio.total_equity >= 1000 else "bright_red"
        
        # Calculate daily P&L dollar and percent
        actual_pnl_dollar = portfolio.unrealized_pnl + portfolio.realized_pnl
        # Prefer provided daily_pnl_percent if populated; otherwise compute against total equity
        if portfolio.daily_pnl_percent is not None and abs(portfolio.daily_pnl_percent) > 0:
            actual_pnl_percent = portfolio.daily_pnl_percent
        else:
            base = portfolio.total_equity if portfolio.total_equity > 0 else 1.0
            actual_pnl_percent = (actual_pnl_dollar / base) * 100.0
        
        pnl_color = "bright_green" if actual_pnl_percent >= 0 else "bright_red"
        pnl_symbol = "+" if actual_pnl_percent >= 0 else ""
        
        table.add_row("Total Equity", f"${portfolio.total_equity:,.2f}", Text("", style=equity_color))
        table.add_row("Cash Balance", f"${portfolio.cash_balance:,.2f}", "")
        table.add_row("Positions", str(portfolio.positions_count), "")
        table.add_row("Daily P&L", f"${actual_pnl_dollar:,.2f}", 
                     Text(f"{pnl_symbol}{actual_pnl_percent:.2f}%", style=pnl_color))
        table.add_row("Market", portfolio.market_session.title(), "")
        
        return Panel(table, title="Portfolio", style="green", box=ROUNDED)
    
    def render_actions(self) -> Panel:
        """Render scheduled actions"""
        if not self.current_status:
            return Panel("No action data", title="Actions", style="dim")
        
        table = Table(show_header=True, header_style="bold magenta", box=MINIMAL)
        table.add_column("Action", style="bright_white", width=12)
        table.add_column("Status", width=8)
        table.add_column("Next Run", width=10, style="dim")
        
        for action in self.current_status.scheduled_actions:
            status_color = self.action_colors.get(action.status, "white")
            status_symbol = {
                ActionStatus.PENDING: "⏳",
                ActionStatus.RUNNING: "🏃", 
                ActionStatus.COMPLETED: "✅",
                ActionStatus.FAILED: "❌",
                ActionStatus.SKIPPED: "⏭️"
            }.get(action.status, "❓")
            
            # Format next run time
            try:
                raw = action.next_run
                if not raw:
                    raise ValueError("missing next_run")
                # Handle Zulu suffix and timezone-aware parsing
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                # Convert to ET if available
                if ZoneInfo is not None:
                    et = ZoneInfo("America/New_York")
                    dt = dt.astimezone(et)
                next_run_str = dt.strftime("%H:%M ET") if ZoneInfo is not None else dt.strftime("%H:%M")
            except Exception:
                next_run_str = "Unknown"
            
            table.add_row(
                action.name.replace(" ", "\n"),  # Break long names
                Text(f"{status_symbol} {action.status.value}", style=status_color),
                next_run_str
            )
        
        return Panel(table, title="Scheduled Actions", style="magenta", box=ROUNDED)
    
    def render_system(self) -> Panel:
        """Render system metrics"""
        if not self.current_status:
            return Panel("No system data", title="System", style="dim")
        
        system = self.current_status.system
        
        # System stats
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="yellow", width=8)
        table.add_column("Value", style="bright_white", justify="right")
        
        # Color code based on usage
        cpu_color = "bright_red" if system.cpu_percent > 80 else "bright_yellow" if system.cpu_percent > 60 else "bright_green"
        mem_color = "bright_red" if system.memory_percent > 80 else "bright_yellow" if system.memory_percent > 60 else "bright_green"
        
        # Format uptime
        uptime_hours = system.uptime_seconds // 3600
        uptime_mins = (system.uptime_seconds % 3600) // 60
        
        table.add_row("CPU", Text(f"{system.cpu_percent:.1f}%", style=cpu_color))
        table.add_row("Memory", Text(f"{system.memory_percent:.1f}%", style=mem_color))
        table.add_row("Disk", f"{system.disk_percent:.1f}%")
        table.add_row("Load", f"{system.load_average[0]:.2f}")
        table.add_row("Uptime", f"{uptime_hours}h {uptime_mins}m")
        table.add_row("Processes", str(system.python_processes))
        
        return Panel(table, title="System", style="yellow", box=ROUNDED)
    
    def render_logs(self) -> Panel:
        """Render recent log entries"""
        if not self.current_status or not self.current_status.recent_logs:
            return Panel("No recent logs", title="Recent Activity", style="dim")
        
        # Show last 5 log entries
        log_lines = []
        for log in self.current_status.recent_logs[:5]:
            try:
                timestamp = datetime.fromisoformat(log.timestamp.replace("Z", "")).strftime("%H:%M:%S")
            except:
                timestamp = "??:??:??"
            
            level_colors = {
                "INFO": "bright_blue",
                "WARNING": "bright_yellow", 
                "ERROR": "bright_red",
                "DEBUG": "dim"
            }
            level_color = level_colors.get(log.level, "white")
            
            log_line = Text()
            log_line.append(f"[{timestamp}] ", style="dim")
            log_line.append(f"{log.level:5s} ", style=level_color)
            log_line.append(f"{log.component}: ", style="cyan")
            log_line.append(log.message, style="white")
            
            log_lines.append(log_line)
        
        # Join with newlines
        log_content = Text("\n").join(log_lines) if log_lines else Text("No logs available", style="dim")
        
        # Include last in-loop error if present
        if self._last_error:
            err = Text(self._last_error, style="bright_red")
            log_content = Text("\n").join([err, log_content]) if log_content else err
        return Panel(log_content, title="Recent Activity", style="white", box=ROUNDED)
    
    def update_display(self, layout: Layout) -> None:
        """Update all layout regions with current data"""
        self.current_status = self.status_manager.load_status()
        
        layout["header"].update(self.render_header())
        layout["components"].update(self.render_components())
        layout["portfolio"].update(self.render_portfolio())
        layout["actions"].update(self.render_actions())
        layout["system"].update(self.render_system())
        layout["footer"].update(self.render_logs())
    
    def run_dashboard(self, duration: Optional[int] = None) -> None:
        """Run the live dashboard"""
        self.running = True
        layout = self.create_layout()
        
        with Live(
            layout,
            console=self.console,
            refresh_per_second=1 / self.refresh_rate,
            transient=False,
            screen=self.console.is_terminal,  # use alt screen only on real TTY
            auto_refresh=False,
        ) as live:
            
            start_time = time.time()
            
            while self.running:
                try:
                    self.update_display(layout)
                    live.update(layout)
                    live.refresh()  # Manual refresh to control timing
                    
                    # Check duration limit
                    if duration and (time.time() - start_time) >= duration:
                        break
                    
                    time.sleep(self.refresh_rate)
                    
                except KeyboardInterrupt:
                    self.running = False
                    break
                except Exception as e:
                    # Avoid printing to console during Live rendering; render error inside footer instead
                    self._last_error = f"Error updating display: {e}"
                    layout["footer"].update(Panel(Text(self._last_error), title="Error", style="red", box=ROUNDED))
                    live.refresh()
                    time.sleep(self.refresh_rate)
    
    def stop_dashboard(self) -> None:
        """Stop the dashboard"""
        self.running = False


def main():
    """Main entry point for TUI controller"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AutoPilot TUI Dashboard")
    parser.add_argument("--status-file", default="/tmp/autopilot_status.json",
                       help="Status file path (default: /tmp/autopilot_status.json)")
    parser.add_argument("--refresh", type=int, default=2,
                       help="Refresh rate in seconds (default: 2)")
    parser.add_argument("--duration", type=int,
                       help="Run for specified duration in seconds")
    parser.add_argument("--test", action="store_true",
                       help="Run with mock data for testing")
    
    args = parser.parse_args()
    
    # Create test data if requested
    if args.test:
        status_manager = StatusManager(args.status_file)
        test_status = status_manager.create_default_status()
        
        # Update with more realistic test data
        test_status.components[0].status = ComponentStatus.HEALTHY
        test_status.components[0].message = "Trading script running normally"
        test_status.components[0].pid = 12345
        test_status.components[1].status = ComponentStatus.WARNING  
        test_status.components[1].message = "Connection latency high"
        test_status.portfolio.total_equity = 1245.67
        test_status.portfolio.daily_pnl_percent = 2.34
        test_status.system.cpu_percent = 45.2
        test_status.system.memory_percent = 67.8
        test_status.system.uptime_seconds = 7234  # ~2 hours
        
        status_manager.save_status(test_status)
        print(f"Created test data in {args.status_file}")
    
    # Run dashboard
    controller = TUIController(args.status_file, args.refresh)
    
    try:
        print(f"Starting AutoPilot TUI Dashboard...")
        print(f"Status file: {args.status_file}")
        print(f"Refresh rate: {args.refresh}s")
        print("Press Ctrl+C to exit")
        controller.run_dashboard(args.duration)
    except KeyboardInterrupt:
        print("\nDashboard stopped by user")
    finally:
        controller.stop_dashboard()


if __name__ == "__main__":
    main()
