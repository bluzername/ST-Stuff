#!/usr/bin/env python3
"""
Client Portal Trade Executor

Drop-in replacement for ib_executor.py using Client Portal REST API.
Same CSV monitoring, same command-line interface, different backend.

Author: Someone who thinks executors should execute things
"""

import asyncio
import argparse
import logging
import sys
import time
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional

# Local imports
from csv_monitor import CSVTradeMonitor
from cp_connection import ClientPortalConnection, ClientPortalError
from execution_logger import ExecutionLogger


class ClientPortalExecutor:
    """Main executor using Client Portal API instead of TWS"""
    
    def __init__(self, config_path: str = "cp_config.yaml"):
        # Load configuration
        self.config_path = config_path
        
        # Initialize components
        self.connection = ClientPortalConnection(config_path)
        self.execution_logger = ExecutionLogger(
            self.connection.config['logging']['files']['execution_log']
        )
        
        # CSV monitors for each data directory
        self.csv_monitors = []
        for data_dir in self.connection.config['monitoring']['data_directories']:
            monitor = CSVTradeMonitor(
                data_dir=data_dir,
                checkpoint_file=f"{data_dir}/.cp_checkpoint.json"
            )
            self.csv_monitors.append(monitor)
        
        self.logger = logging.getLogger(__name__)
        
        # Setup logging: console + file (cp_api.log) so monitor can see connection messages
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

            try:
                api_log_path = self.connection.config['logging']['files']['api_log']
                file_handler = logging.FileHandler(api_log_path)
                file_formatter = logging.Formatter(self.connection.config['logging']['format'])
                file_handler.setFormatter(file_formatter)
                self.logger.addHandler(file_handler)
            except Exception:
                # If file handler fails, we still have console output
                pass

            self.logger.setLevel(logging.INFO)
    
    def connect_to_client_portal(self, allow_reauth: bool = True) -> bool:
        """Connect to Client Portal Gateway"""
        self.logger.info("Connecting to Client Portal Gateway...")
        
        # Check if gateway is accessible
        if not self.connection.check_connection():
            self.logger.error("Client Portal Gateway not accessible")
            return False
        
        # Authenticate
        if not self.connection.authenticate(allow_reauth=allow_reauth):
            self.logger.error("Authentication failed")
            return False
        
        # Get accounts
        accounts = self.connection.get_accounts()
        if not accounts:
            self.logger.error("No trading accounts available")
            return False
        
        mode = self.connection.trading_config['mode'].upper()
        self.logger.info(f"Connected to Client Portal in {mode} mode")
        self.logger.info(f"Using account: {self.connection.account_id}")
        
        return True
    
    def get_all_pending_trades(self, target_date: str = None) -> List[Dict[str, Any]]:
        """Get pending trades from all monitored CSV directories"""
        all_trades = []
        
        for monitor in self.csv_monitors:
            try:
                trades = monitor.get_all_pending_trades()
                
                # Filter by date if specified
                if target_date:
                    trades = [t for t in trades if t['csv_date'] == target_date]
                
                # Add source directory info
                for trade in trades:
                    trade['monitor_dir'] = str(monitor.data_dir)
                
                all_trades.extend(trades)
                
                self.logger.info(f"Found {len(trades)} pending trades in {monitor.data_dir}")
                
            except Exception as e:
                self.logger.error(f"Error getting trades from {monitor.data_dir}: {e}")
        
        return all_trades
    
    def validate_trades(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate trades against safety limits"""
        valid_trades = []
        
        for trade in trades:
            if self.connection.validate_order(trade):
                valid_trades.append(trade)
            else:
                self.logger.warning(f"Trade validation failed: {trade}")
        
        return valid_trades
    
    def display_trades(self, trades: List[Dict[str, Any]], title: str = "Trades"):
        """Display trades in a formatted table"""
        if not trades:
            print(f"\n{title}: None")
            return
        
        print(f"\n{title} ({len(trades)} total):")
        print("-" * 80)
        print(f"{'Action':<4} {'Ticker':<8} {'Qty':<8} {'Price':<10} {'Type':<4} {'Date':<12} {'Source':<15}")
        print("-" * 80)
        
        for trade in trades:
            print(f"{trade['action']:<4} {trade['ticker']:<8} {trade['quantity']:<8.0f} "
                  f"${trade['price']:<9.2f} {trade['order_type']:<4} {trade['csv_date']:<12} "
                  f"{trade['source']:<15}")
        
        print("-" * 80)
    
    def execute_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Execute a single trade via Client Portal"""
        ticker = trade_data['ticker']
        action = trade_data['action']
        quantity = trade_data['quantity']
        price = trade_data.get('price', 0)
        
        self.logger.info(f"Executing {action} {quantity} {ticker} @ ${price:.2f}")
        
        try:
            # Place order through Client Portal
            result = self.connection.place_order(trade_data)
            
            if not result.order_id:
                self.logger.error(f"Failed to place order for {ticker}: {result.message}")
                return False
            
            order_id = result.order_id
            self.logger.info(f"Order placed successfully - ID: {order_id}")
            
            # Log order placement
            self.execution_logger.log_order_placement({
                'order_id': order_id,
                'ticker': ticker,
                'action': action,
                'quantity': quantity,
                'order_type': trade_data.get('order_type', 'LMT'),
                'price': price,
                'csv_source': trade_data.get('source', ''),
                'csv_date': trade_data.get('csv_date', ''),
                'csv_index': trade_data.get('csv_index', '')
            })
            
            # Wait a moment for order to be processed
            time.sleep(2)
            
            # Check order status
            order_status = self.connection.get_order_status(order_id)
            status = order_status.get('status', order_status.get('orderStatus', 'unknown'))
            
            self.logger.info(f"Order {order_id} status: {status}")
            
            # Update execution log with status
            status_data = {
                'status': status,
                'execution_date': datetime.now().date().isoformat(),
                'execution_time': datetime.now().time().isoformat(),
                'notes': f'Order placed via Client Portal API'
            }
            
            # If filled, get fill details
            if status.lower() in ['filled', 'complete']:
                executed_price = order_status.get('avgPrice', order_status.get('executedPrice', price))
                commission = order_status.get('commission', 0)
                total_cost = abs(quantity * executed_price) + abs(commission)
                
                status_data.update({
                    'executed_price': executed_price,
                    'commission': commission,
                    'total_cost': total_cost,
                    'notes': 'Order filled successfully'
                })
                
                self.logger.info(f"Order {order_id} filled @ ${executed_price:.2f}")
            
            self.execution_logger.update_execution_status(order_id, status_data)
            
            # Mark as processed in CSV monitor
            for monitor in self.csv_monitors:
                if str(monitor.data_dir) == trade_data.get('monitor_dir'):
                    monitor.mark_trade_processed(trade_data, order_id)
                    break
            
            return status.lower() in ['filled', 'complete', 'submitted', 'presubmitted']
            
        except ClientPortalError as e:
            self.logger.error(f"Client Portal error executing trade {ticker}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error executing trade {ticker}: {e}")
            return False
    
    def execute_trades(self, trades: List[Dict[str, Any]], confirm: bool = True) -> int:
        """Execute a list of trades"""
        if not trades:
            self.logger.info("No trades to execute")
            return 0
        
        # Show summary
        self.display_trades(trades, "Trades to Execute")
        
        # Confirmation
        if confirm:
            response = input(f"\nExecute {len(trades)} trades? [y/N]: ").strip().lower()
            if response not in ['y', 'yes']:
                print("Execution cancelled")
                return 0
        
        # Check daily limits
        today = datetime.now().date().isoformat()
        daily_count = self.execution_logger.get_daily_trade_count(today)
        max_daily = self.connection.safety_config['max_daily_trades']
        
        if daily_count + len(trades) > max_daily:
            self.logger.error(f"Daily trade limit exceeded: {daily_count + len(trades)} > {max_daily}")
            return 0
        
        # Execute trades
        successful = 0
        for i, trade in enumerate(trades, 1):
            print(f"\nExecuting trade {i}/{len(trades)}...")
            
            if self.execute_trade(trade):
                successful += 1
                print(f"✓ Successfully executed {trade['action']} {trade['ticker']}")
            else:
                print(f"✗ Failed to execute {trade['action']} {trade['ticker']}")
            
            # Brief pause between trades for rate limiting
            if i < len(trades):
                time.sleep(1)
        
        self.logger.info(f"Executed {successful}/{len(trades)} trades successfully")
        return successful
    
    def monitor_and_execute(self, poll_interval: int = 60):
        """Continuously monitor CSV files and execute new trades"""
        self.logger.info(f"Starting monitor mode (checking every {poll_interval}s)")
        
        try:
            while True:
                try:
                    # Check for new trades
                    trades = self.get_all_pending_trades()
                    valid_trades = self.validate_trades(trades)
                    
                    if valid_trades:
                        self.logger.info(f"Found {len(valid_trades)} new trades to execute")
                        self.execute_trades(valid_trades, confirm=False)
                    
                    # Wait for next check
                    time.sleep(poll_interval)
                    
                except KeyboardInterrupt:
                    self.logger.info("Monitor interrupted by user")
                    break
                except Exception as e:
                    self.logger.error(f"Error in monitor loop: {e}")
                    time.sleep(poll_interval)
        
        finally:
            self.connection.disconnect()
    
    def show_execution_history(self, days: int = 7):
        """Display recent execution history"""
        df = self.execution_logger.get_execution_history(days)
        
        if df.empty:
            print(f"No executions found in last {days} days")
            return
        
        print(f"\nExecution History (Last {days} days):")
        print("=" * 100)
        
        # Summary stats
        filled = df[df['status'] == 'FILLED']
        total_trades = len(filled)
        total_volume = filled['total_cost'].sum() if 'total_cost' in filled.columns else 0
        
        print(f"Total Executions: {total_trades}")
        print(f"Total Volume: ${total_volume:,.2f}")
        
        # Slippage stats
        slippage_stats = self.execution_logger.get_slippage_stats(days)
        if slippage_stats:
            print(f"Average Slippage: {slippage_stats['mean_slippage_pct']:.2f}%")
        
        # Recent trades
        print(f"\nRecent Executions:")
        print("-" * 100)
        
        # Show last 10 trades
        recent = df.tail(10)
        for _, row in recent.iterrows():
            print(f"{row['execution_date']} {row['execution_time'][:8]} "
                  f"{row['action']:<4} {row['ticker']:<8} "
                  f"{row['quantity']:<6.0f} @ ${row['executed_price']:<8.2f} "
                  f"({row['status']})")
    
    def reconcile_positions(self):
        """Compare Client Portal positions with CSV portfolio"""
        if not self.connection.authenticated:
            print("Not connected to Client Portal - cannot reconcile positions")
            return
        
        # Get Client Portal positions
        cp_positions = self.connection.get_positions()
        
        print("\nClient Portal Positions:")
        print("-" * 60)
        for pos in cp_positions:
            ticker = pos.get('ticker', pos.get('symbol', 'unknown'))
            position = pos.get('position', pos.get('quantity', 0))
            avg_cost = pos.get('avgCost', pos.get('avgPrice', 0))
            market_value = pos.get('marketValue', pos.get('value', 0))
            
            print(f"{ticker:<8} {position:<8.0f} @ ${avg_cost:<8.2f} "
                  f"(${market_value:,.2f})")
        
        # TODO: Compare with CSV portfolio
        print("\nNote: CSV portfolio comparison not yet implemented")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Client Portal Trade Executor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --monitor --data-dir "Start Your Own"
  %(prog)s --execute-pending --date 2025-09-06  
  %(prog)s --dry-run --show-trades
  %(prog)s --show-executions --days 7
        """
    )
    
    # Configuration
    parser.add_argument('--config', default='cp_config.yaml',
                        help='Configuration file path')
    
    # Data source
    parser.add_argument('--data-dir', action='append',
                        help='Data directory to monitor (can be used multiple times)')
    
    # Execution modes
    parser.add_argument('--monitor', action='store_true',
                        help='Continuously monitor CSV files and execute trades')
    parser.add_argument('--execute-pending', action='store_true', 
                        help='Execute all pending trades')
    parser.add_argument('--date', type=str,
                        help='Execute trades for specific date (YYYY-MM-DD)')
    
    # Analysis modes
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be executed without placing orders')
    parser.add_argument('--show-trades', action='store_true',
                        help='Display pending trades')
    parser.add_argument('--show-executions', action='store_true',
                        help='Show execution history')
    parser.add_argument('--reconcile', action='store_true',
                        help='Compare Client Portal positions with CSV portfolio')
    parser.add_argument('--check-connection', action='store_true',
                        help='Check/establish Client Portal connection and exit')
    
    # Options
    parser.add_argument('--days', type=int, default=7,
                        help='Number of days for history (default: 7)')
    parser.add_argument('--no-confirm', action='store_true',
                        help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    # Create executor
    try:
        executor = ClientPortalExecutor(args.config)
    except Exception as e:
        print(f"Failed to initialize executor: {e}")
        return 1
    
    # Override data directories if specified
    if args.data_dir:
        executor.csv_monitors = []
        for data_dir in args.data_dir:
            monitor = CSVTradeMonitor(
                data_dir=data_dir,
                checkpoint_file=f"{data_dir}/.cp_checkpoint.json"
            )
            executor.csv_monitors.append(monitor)
    
    # Handle different modes
    try:
        if args.check_connection:
            ok = executor.connect_to_client_portal(allow_reauth=False)
            # Always disconnect cleanly
            executor.connection.disconnect()
            return 0 if ok else 1

        if args.show_trades or args.dry_run:
            # Show trades without connecting to Client Portal
            trades = executor.get_all_pending_trades(args.date)
            valid_trades = executor.validate_trades(trades)
            executor.display_trades(valid_trades, "Pending Trades")
            
            if args.dry_run and valid_trades:
                print(f"\nDRY RUN: Would execute {len(valid_trades)} trades")
            
        elif args.show_executions:
            executor.show_execution_history(args.days)
            
        elif args.monitor:
            # Monitor mode - requires Client Portal connection
            if not executor.connect_to_client_portal():
                return 1
                
            poll_interval = executor.connection.config['monitoring']['poll_interval']
            executor.monitor_and_execute(poll_interval)
            
        elif args.execute_pending or args.reconcile:
            # Execution modes - require Client Portal connection  
            if not executor.connect_to_client_portal():
                return 1
                
            try:
                if args.execute_pending:
                    trades = executor.get_all_pending_trades(args.date)
                    valid_trades = executor.validate_trades(trades)
                    executor.execute_trades(valid_trades, confirm=not args.no_confirm)
                
                elif args.reconcile:
                    executor.reconcile_positions()
            
            finally:
                executor.connection.disconnect()
            
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
