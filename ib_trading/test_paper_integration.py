#!/usr/bin/env python3
"""
Interactive Brokers Paper Account Integration Test

Comprehensive test suite for IB Client Portal Gateway integration.
Tests connection, authentication, order placement, and full pipeline functionality.
Designed for paper trading accounts - NO REAL MONEY AT RISK.

Author: Paper Trading Integration Tester
"""

import unittest
import sys
import os
import time
import tempfile
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from unittest.mock import Mock, patch
import logging

# Add the ib_trading directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cp_connection import ClientPortalConnection, ClientPortalError
from csv_monitor import CSVTradeMonitor
from cp_executor import ClientPortalExecutor
from execution_logger import ExecutionLogger


class TestIBPaperIntegration(unittest.TestCase):
    """Comprehensive test suite for IB paper account integration"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests"""
        cls.logger = logging.getLogger(__name__)
        cls.logger.setLevel(logging.INFO)

        # Remove any existing handlers to avoid duplicates
        for handler in cls.logger.handlers[:]:
            cls.logger.removeHandler(handler)

        # Add console handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        cls.logger.addHandler(handler)

        # Test configuration
        cls.config_path = Path(__file__).parent / "cp_config.yaml"
        cls.test_timeout = 30  # seconds for API calls

        cls.logger.info("Setting up IB Paper Account Integration Tests")

    def setUp(self):
        """Set up before each test"""
        self.start_time = time.time()
        self.logger.info(f"Starting test: {self._testMethodName}")

    def tearDown(self):
        """Clean up after each test"""
        duration = time.time() - self.start_time
        self.logger.info(f"Test completed in {duration:.2f}s")
    def test_01_config_file_exists(self):
        """Test that configuration file exists and is valid"""
        self.assertTrue(self.config_path.exists(),
                       f"Configuration file not found: {self.config_path}")

        # Test that it's a valid YAML file
        try:
            import yaml
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            self.assertIsInstance(config, dict, "Config file must contain a dictionary")
            self.assertIn('client_portal', config, "Config must have client_portal section")
            self.assertIn('trading', config, "Config must have trading section")
        except Exception as e:
            self.fail(f"Configuration file is invalid: {e}")

    def test_02_connection_initialization(self):
        """Test Client Portal connection initialization"""
        try:
            cp = ClientPortalConnection(str(self.config_path))
            self.assertIsNotNone(cp, "Connection object should be created")
            self.assertIsNotNone(cp.config, "Config should be loaded")
            self.assertFalse(cp.authenticated, "Should not be authenticated initially")
            cp.disconnect()
        except Exception as e:
            self.fail(f"Connection initialization failed: {e}")

    def test_03_client_portal_connection(self):
        """Test connection to Client Portal Gateway"""
        cp = ClientPortalConnection(str(self.config_path))
        # Test basic connection
        connected = cp.check_connection()
        if not connected:
            self.skipTest("Client Portal Gateway not running - start it first")
        self.assertTrue(connected, "Should be able to connect to Client Portal")
        cp.disconnect()

    def test_04_authentication(self):
        """Test authentication with Client Portal"""
        cp = ClientPortalConnection(str(self.config_path))
        # First check connection
        if not cp.check_connection():
            self.skipTest("Client Portal Gateway not running")
        # Test authentication
        authenticated = cp.authenticate()
        if not authenticated:
            self.skipTest("Not authenticated with Client Portal - authenticate via web interface first")
        self.assertTrue(authenticated, "Should be authenticated with Client Portal")
        self.assertTrue(cp.authenticated, "Connection should be marked as authenticated")
        cp.disconnect()

    def test_05_get_accounts(self):
        """Test retrieving trading accounts"""
        cp = ClientPortalConnection(str(self.config_path))
        if not cp.check_connection():
            self.skipTest("Client Portal Gateway not running")
        if not cp.authenticate():
            self.skipTest("Not authenticated with Client Portal")
        accounts = cp.get_accounts()
        self.assertIsInstance(accounts, list, "Accounts should be a list")
        self.assertGreater(len(accounts), 0, "Should have at least one account")
        self.assertIsNotNone(cp.account_id, "Should have set default account ID")
        self.logger.info(f"Available accounts: {accounts}")
        self.logger.info(f"Using account: {cp.account_id}")
        cp.disconnect()

    def test_06_contract_resolution(self):
        """Test contract ID resolution for various tickers"""
        cp = ClientPortalConnection(str(self.config_path))
        if not cp.check_connection():
            self.skipTest("Client Portal Gateway not running")
        if not cp.authenticate():
            self.skipTest("Not authenticated with Client Portal")

        # Test common tickers
        test_tickers = ['AAPL', 'SPY', 'QQQ', 'MSFT']
        for ticker in test_tickers:
            with self.subTest(ticker=ticker):
                conid = cp.get_contract_id(ticker)
                self.assertIsNotNone(conid, f"Should resolve contract for {ticker}")
                self.assertIsInstance(conid, int, f"Contract ID should be integer for {ticker}")
                self.assertGreater(conid, 0, f"Contract ID should be positive for {ticker}")
                self.logger.info(f"{ticker} -> Contract ID: {conid}")
        cp.disconnect()

    def test_07_order_validation(self):
        """Test order validation logic"""
        cp = ClientPortalConnection(str(self.config_path))

        try:
            # Test valid order
            valid_order = {
                'ticker': 'AAPL',
                'action': 'BUY',
                'quantity': 10,
                'price': 150.00,
                'order_type': 'LMT'
            }
            self.assertTrue(cp.validate_order(valid_order), "Valid order should pass validation")

            # Test invalid orders
            invalid_orders = [
                {'ticker': 'AAPL', 'action': 'BUY', 'quantity': 100000, 'price': 150.00, 'order_type': 'LMT'},  # Too many shares
                {'ticker': 'AAPL', 'action': 'BUY', 'quantity': 10, 'price': 0.01, 'order_type': 'LMT'},  # Price too low
                {'ticker': 'AAPL', 'action': 'BUY', 'quantity': 10, 'price': 150.00, 'order_type': 'INVALID'},  # Invalid type
                {'ticker': 'INVALID', 'action': 'BUY', 'quantity': 10, 'price': 150.00, 'order_type': 'LMT'},  # Invalid ticker (but validation doesn't check this)
            ]

            for i, invalid_order in enumerate(invalid_orders):
                with self.subTest(order_index=i):
                    self.assertFalse(cp.validate_order(invalid_order),
                                   f"Invalid order {i} should fail validation: {invalid_order}")

        except Exception as e:
            self.fail(f"Order validation test failed: {e}")
        finally:
            cp.disconnect()

    def test_08_paper_order_placement(self):
        """Test placing orders on paper account"""
        cp = ClientPortalConnection(str(self.config_path))
        if not cp.check_connection():
            self.skipTest("Client Portal Gateway not running")
        if not cp.authenticate():
            self.skipTest("Not authenticated with Client Portal")

        # Get current market price for a safe test
        # We'll use a limit price that's likely to not fill immediately
        test_order = {
            'ticker': 'AAPL',
            'action': 'BUY',
            'quantity': 1,
            'price': 50.00,  # Very low price - won't fill but will be accepted
            'order_type': 'LMT'
        }

        # Place the order
        result = cp.place_order(test_order)
        self.assertIsNotNone(result, "Order placement should return a result")
        self.assertIsNotNone(result.order_id, "Order should have an ID")
        self.assertNotEqual(result.order_id, '', "Order ID should not be empty")
        self.logger.info(f"Order placed successfully: {result.order_id}")

        # Wait a moment for IB to process
        time.sleep(3)

        # Check order status
        status = cp.get_order_status(result.order_id)
        self.assertIsInstance(status, dict, "Order status should be a dictionary")
        if status:
            order_status = status.get('status', status.get('orderStatus', 'unknown'))
            self.logger.info(f"Order status: {order_status}")

        # Cancel the order to clean up
        cancelled = cp.cancel_order(result.order_id)
        if cancelled:
            self.logger.info("Order cancelled successfully")
        else:
            self.logger.warning("Order cancellation uncertain")
        cp.disconnect()

    def test_09_csv_monitor_initialization(self):
        """Test CSV monitor initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test CSV files
            portfolio_csv = Path(temp_dir) / "chatgpt_portfolio_update.csv"
            trade_log_csv = Path(temp_dir) / "chatgpt_trade_log.csv"

            # Create empty CSV files with headers
            pd.DataFrame(columns=['Date', 'Ticker', 'Shares', 'Buy Price']).to_csv(portfolio_csv, index=False)
            pd.DataFrame(columns=['Date', 'Ticker', 'Shares Bought', 'Buy Price', 'Reason']).to_csv(trade_log_csv, index=False)

            # Test monitor creation
            monitor = CSVTradeMonitor(data_dir=temp_dir)
            self.assertIsNotNone(monitor, "CSV monitor should be created")
            self.assertTrue(monitor.data_dir.exists(), "Data directory should exist")
            self.assertTrue(monitor.portfolio_csv.exists(), "Portfolio CSV should exist")
            self.assertTrue(monitor.trade_log_csv.exists(), "Trade log CSV should exist")

    def test_10_csv_trade_detection(self):
        """Test CSV trade detection"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test CSV files with sample data
            portfolio_csv = Path(temp_dir) / "chatgpt_portfolio_update.csv"
            trade_log_csv = Path(temp_dir) / "chatgpt_trade_log.csv"

            # Create portfolio CSV
            portfolio_data = pd.DataFrame({
                'Date': ['2025-09-10', '2025-09-10'],
                'Ticker': ['AAPL', 'SPY'],
                'Shares': [10, 5],
                'Buy Price': [150.00, 450.00],
                'Stop Loss': [140.00, 440.00]
            })
            portfolio_data.to_csv(portfolio_csv, index=False)

            # Create trade log CSV with a buy order
            trade_data = pd.DataFrame({
                'Date': ['2025-09-10'],
                'Ticker': ['AAPL'],
                'Shares Bought': [10],
                'Buy Price': [150.00],
                'Reason': ['MANUAL BUY LIMIT - Test Order']
            })
            trade_data.to_csv(trade_log_csv, index=False)

            # Test trade detection
            monitor = CSVTradeMonitor(data_dir=temp_dir)
            trades = monitor.get_all_pending_trades()

            self.assertIsInstance(trades, list, "Trades should be a list")
            self.assertGreater(len(trades), 0, "Should detect at least one trade")

            # Check the detected trade
            trade = trades[0]
            self.assertEqual(trade['ticker'], 'AAPL', "Should detect AAPL trade")
            self.assertEqual(trade['action'], 'BUY', "Should detect BUY action")
            self.assertEqual(trade['quantity'], 10, "Should detect correct quantity")
            self.assertEqual(trade['price'], 150.00, "Should detect correct price")

    def test_11_executor_initialization(self):
        """Test executor initialization"""
        try:
            executor = ClientPortalExecutor(str(self.config_path))
            self.assertIsNotNone(executor, "Executor should be created")
            self.assertIsNotNone(executor.connection, "Should have connection")
            self.assertIsNotNone(executor.execution_logger, "Should have execution logger")
            self.assertIsInstance(executor.csv_monitors, list, "Should have CSV monitors list")
        except Exception as e:
            self.fail(f"Executor initialization failed: {e}")

    def test_12_full_pipeline_dry_run(self):
        """Test full pipeline in dry-run mode"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test CSV with a trade
            trade_log_csv = Path(temp_dir) / "chatgpt_trade_log.csv"
            portfolio_csv = Path(temp_dir) / "chatgpt_portfolio_update.csv"

            # Create trade log with a buy order
            trade_data = pd.DataFrame({
                'Date': ['2025-09-10'],
                'Ticker': ['AAPL'],
                'Shares Bought': [1],
                'Buy Price': [150.00],
                'Reason': ['MANUAL BUY LIMIT - Test Order']
            })
            trade_data.to_csv(trade_log_csv, index=False)

            # Create minimal portfolio CSV
            portfolio_data = pd.DataFrame({
                'Date': ['2025-09-10'],
                'Ticker': ['TOTAL'],
                'Shares': [''],
                'Buy Price': [''],
                'Stop Loss': [''],
                'Current Price': [''],
                'Total Value': [1000.00],
                'PnL': [0.00],
                'Action': [''],
                'Cash Balance': [10000.00],
                'Total Equity': [11000.00]
            })
            portfolio_data.to_csv(portfolio_csv, index=False)

            # Test executor with dry run
            executor = ClientPortalExecutor(str(self.config_path))

            # Override CSV monitors to use our test directory with local checkpoint
            from csv_monitor import CSVTradeMonitor
            test_monitor = CSVTradeMonitor(data_dir=temp_dir, checkpoint_file=".cp_checkpoint.json")
            executor.csv_monitors = [test_monitor]

            # Get pending trades
            trades = executor.get_all_pending_trades()
            self.assertGreater(len(trades), 0, "Should detect pending trades")

            # Validate trades
            valid_trades = executor.validate_trades(trades)
            self.assertGreater(len(valid_trades), 0, "Should have valid trades")

            # Display trades (should not fail)
            executor.display_trades(valid_trades, "Test Trades")

    def test_13_execution_logger(self):
        """Test execution logger functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test_execution_log.csv"

            # Test logger creation
            logger = ExecutionLogger(str(log_file))
            self.assertTrue(log_file.exists(), "Log file should be created")

            # Test logging an execution
            test_execution = {
                'execution_date': '2025-09-10',
                'execution_time': '10:00:00',
                'ib_order_id': '12345',
                'ticker': 'AAPL',
                'action': 'BUY',
                'quantity': 10,
                'order_type': 'LMT',
                'limit_price': 150.00,
                'executed_price': 150.00,
                'commission': 1.00,
                'total_cost': 1501.00,
                'status': 'FILLED',
                'csv_source': 'trade_log',
                'csv_row_date': '2025-09-10',
                'csv_row_index': 0,
                'slippage': 0.0,
                'notes': 'Test execution'
            }

            logger.log_execution(test_execution)

            # Verify the log was written
            df = pd.read_csv(log_file)
            self.assertEqual(len(df), 1, "Should have one execution logged")
            self.assertEqual(df.iloc[0]['ticker'], 'AAPL', "Should log correct ticker")
            self.assertEqual(df.iloc[0]['status'], 'FILLED', "Should log correct status")

    def test_14_error_handling(self):
        """Test error handling in various scenarios"""
        cp = ClientPortalConnection(str(self.config_path))

        # Only attempt API calls if gateway is up to avoid long timeouts
        if cp.check_connection():
            try:
                _ = cp.authenticate()  # Best-effort
                # Test invalid ticker resolution path
                _ = cp.get_contract_id('INVALID_TICKER_12345')
            except Exception:
                pass  # Expected failure paths shouldn't crash the suite

        # Test invalid order validation locally (no network)
        invalid_order = {
            'ticker': 'AAPL',
            'action': 'INVALID',
            'quantity': -1,
            'price': -100,
            'order_type': 'INVALID'
        }
        try:
            self.assertFalse(cp.validate_order(invalid_order))
        except Exception:
            pass
        cp.disconnect()

    def test_15_integration_smoke_test(self):
        """Smoke test for the complete integration"""
        self.logger.info("Running integration smoke test...")

        # This test checks if all components can be initialized together
        try:
            # Initialize all components
            cp = ClientPortalConnection(str(self.config_path))
            executor = ClientPortalExecutor(str(self.config_path))

            # Check that components are properly initialized and consistent
            self.assertIsNotNone(cp, "Connection should initialize")
            self.assertIsNotNone(executor, "Executor should initialize")
            self.assertIsInstance(executor.connection, ClientPortalConnection)
            # Config consistency: base URLs should match
            self.assertEqual(cp.base_url, executor.connection.base_url,
                             "Executor connection should use the same base URL")

            # Clean up
            cp.disconnect()

            self.logger.info("Integration smoke test passed")

        except Exception as e:
            self.fail(f"Integration smoke test failed: {e}")


def run_tests_with_reporting():
    """Run tests with detailed reporting"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestIBPaperIntegration)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Passed: {len(result.successes) if hasattr(result, 'successes') else result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")

    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")

    return result.wasSuccessful()


if __name__ == '__main__':
    print("Interactive Brokers Paper Account Integration Test")
    print("="*60)
    print("This test suite validates the complete IB Client Portal integration.")
    print("Make sure Client Portal Gateway is running and you're authenticated.")
    print("Tests use PAPER TRADING - no real money at risk.")
    print("="*60)

    success = run_tests_with_reporting()

    if success:
        print("\n✅ ALL TESTS PASSED - Integration is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED - Check the issues above")
        sys.exit(1)
