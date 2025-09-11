#!/usr/bin/env python3
"""
Comprehensive test suite for TUI integration
Tests status management, TUI controller, and autopilot integration
"""

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from status_schema import (
    StatusManager, AutopilotStatus, ComponentStatus, ActionStatus,
    ComponentHealth, PortfolioMetrics, ScheduledAction, SystemMetrics, LogEntry
)


class TestStatusManager(unittest.TestCase):
    """Test the status management system"""
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json')
        self.temp_file.close()
        self.manager = StatusManager(self.temp_file.name)
    
    def tearDown(self):
        try:
            os.unlink(self.temp_file.name)
        except FileNotFoundError:
            pass
    
    def test_create_default_status(self):
        """Test default status creation"""
        status = self.manager.create_default_status()
        
        self.assertIsInstance(status, AutopilotStatus)
        self.assertEqual(len(status.components), 4)
        self.assertEqual(status.portfolio.total_equity, 1000.0)
        self.assertEqual(status.portfolio.cash_balance, 1000.0)
        self.assertEqual(len(status.scheduled_actions), 2)
        self.assertGreater(len(status.timestamp), 10)
    
    def test_save_and_load_status(self):
        """Test status file save/load operations"""
        original_status = self.manager.create_default_status()
        original_status.mode = "test"
        original_status.portfolio.total_equity = 1234.56
        
        # Save status
        self.manager.save_status(original_status)
        self.assertTrue(os.path.exists(self.temp_file.name))
        
        # Load status
        loaded_status = self.manager.load_status()
        self.assertEqual(loaded_status.mode, "test")
        self.assertEqual(loaded_status.portfolio.total_equity, 1234.56)
        self.assertEqual(len(loaded_status.components), 4)
    
    def test_update_component_status(self):
        """Test component status updates"""
        # Initialize with default status
        self.manager.save_status(self.manager.create_default_status())
        
        # Update a component
        self.manager.update_component_status(
            "Trading Script", 
            ComponentStatus.HEALTHY,
            "Running normally",
            pid=12345
        )
        
        # Verify update
        status = self.manager.load_status()
        trading_component = next(c for c in status.components if c.name == "Trading Script")
        self.assertEqual(trading_component.status, ComponentStatus.HEALTHY)
        self.assertEqual(trading_component.message, "Running normally")
        self.assertEqual(trading_component.pid, 12345)
    
    def test_update_portfolio_metrics(self):
        """Test portfolio metrics updates"""
        # Initialize with default status
        self.manager.save_status(self.manager.create_default_status())
        
        # Update portfolio
        self.manager.update_portfolio_metrics(
            total_equity=2500.0,
            cash_balance=1500.0,
            positions_count=3,
            market_session="regular"
        )
        
        # Verify update
        status = self.manager.load_status()
        portfolio = status.portfolio
        self.assertEqual(portfolio.total_equity, 2500.0)
        self.assertEqual(portfolio.cash_balance, 1500.0)
        self.assertEqual(portfolio.positions_count, 3)
        self.assertEqual(portfolio.market_session, "regular")
    
    def test_add_log_entry(self):
        """Test log entry addition"""
        # Initialize with default status
        self.manager.save_status(self.manager.create_default_status())
        
        # Add log entries
        self.manager.add_log_entry("INFO", "Test Component", "Test message 1")
        self.manager.add_log_entry("ERROR", "Test Component", "Test message 2", "exec_123")
        
        # Verify logs
        status = self.manager.load_status()
        self.assertEqual(len(status.recent_logs), 2)
        
        # Most recent log should be first
        recent_log = status.recent_logs[0]
        self.assertEqual(recent_log.level, "ERROR")
        self.assertEqual(recent_log.component, "Test Component")
        self.assertEqual(recent_log.message, "Test message 2")
        self.assertEqual(recent_log.execution_id, "exec_123")
    
    def test_malformed_json_handling(self):
        """Test handling of malformed JSON files"""
        # Write malformed JSON
        with open(self.temp_file.name, 'w') as f:
            f.write('{"invalid": "json", "missing": }')
        
        # Should return default status
        status = self.manager.load_status()
        self.assertIsInstance(status, AutopilotStatus)
        self.assertEqual(len(status.components), 4)
    
    def test_missing_file_handling(self):
        """Test handling of missing status file"""
        # Remove the file
        os.unlink(self.temp_file.name)
        
        # Should return default status
        status = self.manager.load_status()
        self.assertIsInstance(status, AutopilotStatus)
        self.assertEqual(len(status.components), 4)


class TestTUIController(unittest.TestCase):
    """Test the TUI controller functionality"""
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json')
        self.temp_file.close()
        self.manager = StatusManager(self.temp_file.name)
        
        # Create test status
        test_status = self.manager.create_default_status()
        test_status.components[0].status = ComponentStatus.HEALTHY
        test_status.components[0].message = "Test message"
        test_status.components[0].pid = 12345
        test_status.portfolio.total_equity = 1250.75
        test_status.portfolio.daily_pnl_percent = 2.5
        
        self.manager.save_status(test_status)
    
    def tearDown(self):
        try:
            os.unlink(self.temp_file.name)
        except FileNotFoundError:
            pass
    
    def test_tui_controller_import(self):
        """Test that TUI controller can be imported"""
        try:
            from tui_controller import TUIController
            controller = TUIController(self.temp_file.name)
            self.assertIsNotNone(controller)
            self.assertEqual(controller.status_manager.status_file, self.temp_file.name)
        except ImportError as e:
            self.fail(f"Could not import TUIController: {e}")
    
    def test_tui_controller_status_colors(self):
        """Test TUI controller color mappings"""
        from tui_controller import TUIController
        
        controller = TUIController(self.temp_file.name)
        
        # Test status color mappings
        self.assertIn(ComponentStatus.HEALTHY, controller.status_colors)
        self.assertIn(ComponentStatus.ERROR, controller.status_colors)
        self.assertEqual(controller.status_colors[ComponentStatus.HEALTHY], "bright_green")
        self.assertEqual(controller.status_colors[ComponentStatus.ERROR], "bright_red")
    
    @patch('psutil.cpu_percent', return_value=45.2)
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_tui_layout_creation(self, mock_disk, mock_memory, mock_cpu):
        """Test TUI layout creation"""
        from tui_controller import TUIController
        
        # Mock memory and disk
        mock_memory.return_value.percent = 67.8
        mock_disk.return_value.percent = 15.5
        
        controller = TUIController(self.temp_file.name)
        layout = controller.create_layout()
        
        # Test layout structure - Rich Layout doesn't support 'in' operator
        # Just verify the layout was created successfully
        self.assertIsNotNone(layout)
        self.assertEqual(layout.name, "root")
        
        # Test that we can access layout regions without errors
        try:
            header_layout = layout["header"]
            body_layout = layout["body"] 
            footer_layout = layout["footer"]
            components_layout = layout["body"]["left"]["components"]
            portfolio_layout = layout["body"]["left"]["portfolio"]
            
            # If we get here, the layout structure is correct
            self.assertIsNotNone(header_layout)
            self.assertIsNotNone(body_layout)
            self.assertIsNotNone(footer_layout)
            self.assertIsNotNone(components_layout)
            self.assertIsNotNone(portfolio_layout)
        except KeyError as e:
            self.fail(f"Layout structure incorrect: {e}")


class TestAutopilotIntegration(unittest.TestCase):
    """Test autopilot.sh integration"""
    
    def setUp(self):
        self.script_path = Path(__file__).parent / "autopilot.sh"
        self.assertTrue(self.script_path.exists(), "autopilot.sh not found")
    
    def test_autopilot_syntax(self):
        """Test autopilot.sh syntax"""
        result = subprocess.run(
            ["bash", "-n", str(self.script_path)],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"Syntax error in autopilot.sh: {result.stderr}")
    
    def test_autopilot_help(self):
        """Test autopilot.sh help output"""
        result = subprocess.run(
            [str(self.script_path), "help"],
            capture_output=True,
            text=True
        )
        
        # Should show usage information
        self.assertIn("Usage:", result.stdout)
        self.assertIn("dashboard", result.stdout)
        self.assertIn("Commands:", result.stdout)
    
    def test_autopilot_status_command(self):
        """Test autopilot.sh status command"""
        result = subprocess.run(
            [str(self.script_path), "status"],
            capture_output=True,
            text=True
        )
        
        # Should indicate autopilot is not running
        self.assertIn("not running", result.stdout.lower())
        self.assertIn("16:15", result.stdout)  # Daily update time
        self.assertIn("09:15", result.stdout)  # Execute time
    
    def test_dashboard_command_help(self):
        """Test dashboard command help"""
        result = subprocess.run(
            [str(self.script_path), "dashboard", "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Should show TUI controller help
        self.assertIn("AutoPilot TUI Dashboard", result.stdout)
        self.assertIn("--refresh", result.stdout)
        self.assertIn("--duration", result.stdout)


class TestIntegrationEndToEnd(unittest.TestCase):
    """End-to-end integration tests"""
    
    def test_status_file_creation_and_dashboard_launch(self):
        """Test complete workflow: status creation -> dashboard launch"""
        temp_dir = tempfile.mkdtemp()
        status_file = os.path.join(temp_dir, "test_status.json")
        
        try:
            # Create status manager and initial status
            manager = StatusManager(status_file)
            initial_status = manager.create_default_status()
            manager.save_status(initial_status)
            
            # Verify file creation
            self.assertTrue(os.path.exists(status_file))
            
            # Test dashboard launch with short duration
            result = subprocess.run([
                str(Path(__file__).parent / "autopilot.sh"),
                "dashboard",
                "--status-file", status_file,
                "--duration", "1"
            ], capture_output=True, text=True, timeout=10)
            
            # Should launch successfully
            self.assertIn("AutoPilot Real-Time Dashboard", result.stdout)
            self.assertIn("Starting TUI dashboard", result.stdout)
            
        finally:
            # Cleanup
            try:
                os.unlink(status_file)
                os.rmdir(temp_dir)
            except (FileNotFoundError, OSError):
                pass
    
    def test_portfolio_csv_integration(self):
        """Test portfolio CSV file integration"""
        csv_file = Path(__file__).parent / "Scripts and CSV Files" / "chatgpt_portfolio_update.csv"
        
        if csv_file.exists():
            # Read CSV file
            with open(csv_file, 'r') as f:
                content = f.read()
            
            # Should contain expected headers
            self.assertIn("Total Equity", content)
            self.assertIn("Cash Balance", content)
            
            # Extract values from last line (should be TOTAL row)
            lines = content.strip().split('\n')
            if len(lines) > 1:
                last_line = lines[-1]
                fields = last_line.split(',')
                if len(fields) >= 12:
                    # Test that we can parse equity and cash values
                    try:
                        equity = float(fields[11]) if fields[11] else 0.0
                        cash = float(fields[10]) if fields[10] else 0.0
                        self.assertIsInstance(equity, float)
                        self.assertIsInstance(cash, float)
                    except (ValueError, IndexError):
                        self.fail("Could not parse portfolio values from CSV")


def run_tests():
    """Run all tests"""
    test_classes = [
        TestStatusManager,
        TestTUIController, 
        TestAutopilotIntegration,
        TestIntegrationEndToEnd
    ]
    
    suite = unittest.TestSuite()
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=== TUI Integration Test Suite ===")
    print()
    
    success = run_tests()
    
    print()
    print("=== Test Summary ===")
    if success:
        print("✅ All tests passed!")
        print()
        print("TUI implementation is working correctly:")
        print("- Status management system functional")
        print("- TUI controller displays data properly")
        print("- Autopilot.sh integration working")
        print("- Error handling robust")
        print("- End-to-end workflow validated")
    else:
        print("❌ Some tests failed!")
        print("Check the test output above for details.")
    
    exit(0 if success else 1)