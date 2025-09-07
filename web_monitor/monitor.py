"""
Pipeline monitoring core - reads CSVs, logs, and calculates metrics
No external dependencies on trading modules, pure data reading
"""

import pandas as pd
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import re

logger = logging.getLogger(__name__)

class PipelineMonitor:
    """Core monitoring logic for the trading pipeline"""
    
    def __init__(self, data_dirs: List[str]):
        self.data_dirs = [Path(d) for d in data_dirs]
        self.logger = logging.getLogger(__name__)
        
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system health and status"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'ib_connection': self._check_ib_connection(),
            'csv_status': self._check_csv_files(),
            'trading_mode': self._detect_trading_mode(),
            'last_activity': self._get_last_activity(),
            'monitoring_dirs': [str(d) for d in self.data_dirs if d.exists()]
        }
        return status
    
    def get_current_portfolio(self) -> List[Dict[str, Any]]:
        """Get current portfolio positions from CSV files"""
        portfolio = []
        
        for data_dir in self.data_dirs:
            portfolio_file = data_dir / "chatgpt_portfolio_update.csv"
            if portfolio_file.exists():
                try:
                    df = pd.read_csv(portfolio_file)
                    for _, row in df.iterrows():
                        # Handle NaN values by converting to 0
                        def safe_float(val, default=0.0):
                            try:
                                f = float(val)
                                return 0.0 if pd.isna(f) or f != f else f  # Check for NaN
                            except (ValueError, TypeError):
                                return default
                        
                        portfolio.append({
                            'ticker': str(row.get('Ticker', '')),
                            'shares': safe_float(row.get('Shares', 0)),
                            'cost_basis': safe_float(row.get('Cost Basis', 0)),
                            'current_price': safe_float(row.get('Current Price', 0)),
                            'market_value': safe_float(row.get('Market Value', 0)),
                            'unrealized_pnl': safe_float(row.get('Unrealized PnL', 0)),
                            'stop_loss': safe_float(row.get('Stop Loss', 0)),
                            'source_dir': str(data_dir.name)
                        })
                except Exception as e:
                    self.logger.error(f"Error reading portfolio from {portfolio_file}: {e}")
        
        return portfolio
    
    def get_pending_trades(self) -> List[Dict[str, Any]]:
        """Get trades that haven't been executed yet"""
        pending = []
        
        for data_dir in self.data_dirs:
            trades_file = data_dir / "chatgpt_trade_log.csv"
            checkpoint_file = data_dir / ".ib_checkpoint.json"
            
            if not trades_file.exists():
                continue
                
            try:
                # Load checkpoint to see what's been processed
                checkpoint = {}
                if checkpoint_file.exists():
                    with open(checkpoint_file, 'r') as f:
                        checkpoint = json.load(f)
                
                last_index = checkpoint.get('last_trade_log_index', -1)
                processed_orders = checkpoint.get('processed_orders', [])
                
                # Read trades CSV
                df = pd.read_csv(trades_file)
                
                for idx, row in df.iterrows():
                    if idx <= last_index:
                        continue  # Already processed
                    
                    # Determine action and create trade record
                    shares_bought = row.get('Shares Bought', 0)
                    shares_sold = row.get('Shares Sold', 0)
                    
                    # Use the same safe_float function
                    def safe_float(val, default=0.0):
                        try:
                            f = float(val)
                            return 0.0 if pd.isna(f) or f != f else f
                        except (ValueError, TypeError):
                            return default
                    
                    if pd.notna(shares_bought) and safe_float(shares_bought) > 0:
                        trade = {
                            'date': str(row.get('Date', '')),
                            'ticker': str(row.get('Ticker', '')),
                            'action': 'BUY',
                            'quantity': safe_float(shares_bought),
                            'price': safe_float(row.get('Buy Price', 0)),
                            'reason': str(row.get('Reason', '')),
                            'source_dir': str(data_dir.name),
                            'csv_index': idx
                        }
                        trade['validation_status'] = self._validate_trade(trade)
                        pending.append(trade)
                    
                    if pd.notna(shares_sold) and safe_float(shares_sold) > 0:
                        trade = {
                            'date': str(row.get('Date', '')),
                            'ticker': str(row.get('Ticker', '')),
                            'action': 'SELL',
                            'quantity': safe_float(shares_sold),
                            'price': safe_float(row.get('Sell Price', 0)),
                            'reason': str(row.get('Reason', '')),
                            'source_dir': str(data_dir.name),
                            'csv_index': idx
                        }
                        trade['validation_status'] = self._validate_trade(trade)
                        pending.append(trade)
                        
            except Exception as e:
                self.logger.error(f"Error reading trades from {trades_file}: {e}")
        
        return pending
    
    def get_execution_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get IB execution history"""
        executions = []
        
        for data_dir in self.data_dirs:
            exec_file = data_dir / "ib_execution_log.csv"
            if not exec_file.exists():
                continue
                
            try:
                df = pd.read_csv(exec_file)
                
                # Filter by date if specified
                if days > 0:
                    cutoff = datetime.now() - timedelta(days=days)
                    df['execution_date'] = pd.to_datetime(df['execution_date'])
                    df = df[df['execution_date'] >= cutoff]
                
                for _, row in df.iterrows():
                    execution = {
                        'execution_date': str(row.get('execution_date', '')),
                        'execution_time': str(row.get('execution_time', '')),
                        'order_id': str(row.get('ib_order_id', '')),
                        'ticker': str(row.get('ticker', '')),
                        'action': str(row.get('action', '')),
                        'quantity': float(row.get('quantity', 0)),
                        'executed_price': float(row.get('executed_price', 0)),
                        'commission': float(row.get('commission', 0)),
                        'total_cost': float(row.get('total_cost', 0)),
                        'status': str(row.get('status', '')),
                        'slippage': float(row.get('slippage', 0)),
                        'source_dir': str(data_dir.name)
                    }
                    executions.append(execution)
                    
            except Exception as e:
                self.logger.error(f"Error reading executions from {exec_file}: {e}")
        
        return sorted(executions, key=lambda x: f"{x['execution_date']} {x['execution_time']}", reverse=True)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics"""
        portfolio = self.get_current_portfolio()
        executions = self.get_execution_history(days=30)
        
        # Current portfolio metrics
        total_value = sum(p['market_value'] for p in portfolio)
        total_pnl = sum(p['unrealized_pnl'] for p in portfolio)
        total_positions = len([p for p in portfolio if p['shares'] > 0])
        
        # Execution metrics
        filled_orders = [e for e in executions if e['status'] == 'FILLED']
        total_volume = sum(abs(e['total_cost']) for e in filled_orders)
        avg_slippage = sum(e['slippage'] for e in filled_orders) / max(len(filled_orders), 1)
        
        # Daily metrics
        today = datetime.now().date()
        today_executions = [e for e in executions if e['execution_date'].startswith(str(today))]
        daily_volume = sum(abs(e['total_cost']) for e in today_executions)
        daily_trades = len(today_executions)
        
        return {
            'portfolio': {
                'total_value': round(total_value, 2),
                'total_pnl': round(total_pnl, 2),
                'total_positions': total_positions,
                'pnl_percentage': round((total_pnl / max(total_value - total_pnl, 1)) * 100, 2)
            },
            'executions': {
                'total_executions': len(filled_orders),
                'total_volume': round(total_volume, 2),
                'avg_slippage': round(avg_slippage, 4),
                'daily_volume': round(daily_volume, 2),
                'daily_trades': daily_trades
            },
            'updated': datetime.now().isoformat()
        }
    
    def get_recent_logs(self, max_lines: int = 100) -> List[Dict[str, str]]:
        """Get recent log entries from IB executor"""
        logs = []
        
        for data_dir in self.data_dirs:
            log_file = data_dir / "ib_executor.log"
            if not log_file.exists():
                continue
                
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    
                # Get last N lines
                recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines
                
                for line in recent_lines:
                    line = line.strip()
                    if line:
                        # Parse log format: timestamp - logger - level - message
                        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (.+?) - (\w+) - (.+)', line)
                        if match:
                            timestamp, logger_name, level, message = match.groups()
                            logs.append({
                                'timestamp': timestamp,
                                'logger': logger_name,
                                'level': level,
                                'message': message,
                                'source_dir': str(data_dir.name)
                            })
                        else:
                            # Fallback for non-standard format
                            logs.append({
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'logger': 'unknown',
                                'level': 'INFO',
                                'message': line,
                                'source_dir': str(data_dir.name)
                            })
                            
            except Exception as e:
                self.logger.error(f"Error reading logs from {log_file}: {e}")
        
        return logs[-max_lines:]  # Return most recent
    
    def _check_ib_connection(self) -> Dict[str, Any]:
        """Check IB connection status from logs"""
        status = {
            'connected': False,
            'last_connection': None,
            'connection_issues': []
        }
        
        logs = self.get_recent_logs(max_lines=50)
        
        for log in reversed(logs):  # Check most recent first
            message = log['message'].lower()
            
            if 'connected to ib' in message:
                status['connected'] = True
                status['last_connection'] = log['timestamp']
                break
            elif any(err in message for err in ['connection failed', 'failed to connect', 'disconnected']):
                status['connected'] = False
                status['connection_issues'].append({
                    'timestamp': log['timestamp'],
                    'message': log['message']
                })
        
        return status
    
    def _check_csv_files(self) -> Dict[str, Any]:
        """Check CSV file status and freshness"""
        csv_status = {}
        
        for data_dir in self.data_dirs:
            dir_status = {
                'portfolio_exists': False,
                'trade_log_exists': False,
                'last_update': None,
                'total_trades': 0
            }
            
            portfolio_file = data_dir / "chatgpt_portfolio_update.csv"
            trade_log_file = data_dir / "chatgpt_trade_log.csv"
            
            if portfolio_file.exists():
                dir_status['portfolio_exists'] = True
                stat = portfolio_file.stat()
                dir_status['last_update'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            if trade_log_file.exists():
                dir_status['trade_log_exists'] = True
                try:
                    df = pd.read_csv(trade_log_file)
                    dir_status['total_trades'] = len(df)
                except:
                    pass
            
            csv_status[str(data_dir.name)] = dir_status
        
        return csv_status
    
    def _detect_trading_mode(self) -> str:
        """Detect if system is in paper or live trading mode"""
        # Check IB config for trading mode
        for data_dir in self.data_dirs:
            config_file = data_dir / "ib_config.yaml"
            if config_file.exists():
                try:
                    import yaml
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
                    return config.get('execution', {}).get('mode', 'unknown')
                except:
                    pass
        
        # Fallback: check logs for mode indication
        logs = self.get_recent_logs(max_lines=50)
        for log in logs:
            if 'paper trading mode' in log['message'].lower():
                return 'paper'
            elif 'live trading mode' in log['message'].lower():
                return 'live'
        
        return 'unknown'
    
    def _get_last_activity(self) -> Optional[str]:
        """Get timestamp of last system activity"""
        latest_time = None
        
        # Check execution log
        executions = self.get_execution_history(days=1)
        if executions:
            latest_exec = executions[0]
            exec_time = f"{latest_exec['execution_date']} {latest_exec['execution_time']}"
            try:
                latest_time = datetime.strptime(exec_time[:19], '%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        # Check log files
        logs = self.get_recent_logs(max_lines=10)
        if logs:
            try:
                log_time = datetime.strptime(logs[-1]['timestamp'][:19], '%Y-%m-%d %H:%M:%S')
                if not latest_time or log_time > latest_time:
                    latest_time = log_time
            except:
                pass
        
        return latest_time.isoformat() if latest_time else None
    
    def _validate_trade(self, trade: Dict[str, Any]) -> str:
        """Basic trade validation"""
        if not trade.get('ticker'):
            return 'INVALID_TICKER'
        
        if trade.get('quantity', 0) <= 0:
            return 'INVALID_QUANTITY'
        
        if trade.get('price', 0) <= 0:
            return 'INVALID_PRICE'
        
        # Check if price is reasonable (basic sanity check)
        price = trade.get('price', 0)
        if price < 0.01 or price > 10000:
            return 'PRICE_OUT_OF_RANGE'
        
        return 'VALID'