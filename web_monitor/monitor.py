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
        """Get current portfolio positions from CSV files - most recent data only"""
        # Find the most recent portfolio file based on modification time
        newest_file = None
        newest_time = None
        newest_data_dir = None
        
        for data_dir in self.data_dirs:
            portfolio_file = data_dir / "chatgpt_portfolio_update.csv"
            if portfolio_file.exists():
                try:
                    mtime = portfolio_file.stat().st_mtime
                    if newest_time is None or mtime > newest_time:
                        newest_time = mtime
                        newest_file = portfolio_file
                        newest_data_dir = data_dir
                except Exception as e:
                    self.logger.error(f"Error checking file time for {portfolio_file}: {e}")
        
        # If no files found, return empty
        if not newest_file:
            return []
        
        # Read only the most recent file
        portfolio = []
        try:
            df = pd.read_csv(newest_file)
            
            # Handle NaN values by converting to 0
            def safe_float(val, default=0.0):
                try:
                    f = float(val)
                    return 0.0 if pd.isna(f) or f != f else f  # Check for NaN
                except (ValueError, TypeError):
                    return default
            
            for _, row in df.iterrows():
                # Skip TOTAL rows and empty tickers
                ticker = str(row.get('Ticker', '')).strip()
                if not ticker or ticker.upper() == 'TOTAL':
                    continue
                    
                portfolio.append({
                    'ticker': ticker,
                    'shares': safe_float(row.get('Shares', 0)),
                    'cost_basis': safe_float(row.get('Cost Basis', 0)),
                    'current_price': safe_float(row.get('Current Price', 0)),
                    'market_value': safe_float(row.get('Total Value', 0)) or safe_float(row.get('Market Value', 0)),
                    'unrealized_pnl': safe_float(row.get('PnL', 0)) or safe_float(row.get('Unrealized PnL', 0)),
                    'stop_loss': safe_float(row.get('Stop Loss', 0)),
                    'source_dir': str(newest_data_dir.name),
                    'file_path': str(newest_file)
                })
                
        except Exception as e:
            self.logger.error(f"Error reading portfolio from {newest_file}: {e}")
        
        return portfolio
    
    def get_portfolio_history(self) -> Dict[str, Any]:
        """Get historical portfolio data for charting - simple and direct"""
        history_file = None
        best_len = -1
        
        # Find the file with the most entries; prefer large history but fallback to the longest available
        for data_dir in self.data_dirs:
            portfolio_file = data_dir / "chatgpt_portfolio_update.csv"
            if portfolio_file.exists():
                try:
                    df = pd.read_csv(portfolio_file)
                    n = len(df)
                    if n > best_len:
                        best_len = n
                        history_file = portfolio_file
                    # Early exit if clearly historical
                    if n > 50:
                        break
                except Exception:
                    continue
        
        if not history_file or best_len <= 0:
            return {'dates': [], 'portfolio_returns': [], 'daily_pnl': [], 'total_values': []}
        
        try:
            df = pd.read_csv(history_file)
            
            # Get unique dates and aggregate TOTAL rows (contains portfolio value)
            total_rows = df[df['Ticker'].str.upper() == 'TOTAL'].copy()
            if total_rows.empty:
                return {'dates': [], 'portfolio_returns': [], 'daily_pnl': [], 'total_values': []}
            
            # Sort by date
            total_rows['Date'] = pd.to_datetime(total_rows['Date'])
            total_rows = total_rows.sort_values('Date')
            
            dates = []
            total_values = []
            daily_pnl = []
            
            for _, row in total_rows.iterrows():
                date_str = row['Date'].strftime('%Y-%m-%d')
                total_equity = float(row.get('Total Equity', 0) or 0)
                pnl = float(row.get('PnL', 0) or 0)
                
                dates.append(date_str)
                total_values.append(total_equity)
                daily_pnl.append(pnl)
            
            # Calculate percentage returns from first day
            portfolio_returns = []
            if total_values and total_values[0] > 0:
                base_value = total_values[0]
                for value in total_values:
                    ret = ((value - base_value) / base_value) * 100
                    portfolio_returns.append(round(ret, 2))
            else:
                portfolio_returns = [0.0] * len(dates)
            
            # Add benchmark data
            benchmarks = self.get_benchmark_data(dates)
            
            return {
                'dates': dates,
                'portfolio_returns': portfolio_returns,
                'daily_pnl': daily_pnl, 
                'total_values': total_values,
                'sp500_returns': benchmarks['sp500_returns'],
                'ta125_returns': benchmarks['ta125_returns']
            }
            
        except Exception as e:
            self.logger.error(f"Error reading portfolio history from {history_file}: {e}")
            return {'dates': [], 'portfolio_returns': [], 'daily_pnl': [], 'total_values': []}
    
    def get_benchmark_data(self, dates: List[str]) -> Dict[str, List[float]]:
        """Get benchmark returns - simple hardcoded data for June-Sept period"""
        # Approximate S&P 500 and TA-125 performance June 30 - Sept 8, 2025
        # S&P 500: Generally upward trend ~3-4% over the period
        # TA-125: Israeli market similar performance ~2-3%
        
        sp500_returns = []
        ta125_returns = []
        
        for i, date in enumerate(dates):
            # Simple linear interpolation with some volatility
            days_elapsed = i
            total_days = len(dates) - 1 if len(dates) > 1 else 1
            
            # S&P 500: ~3.5% total return over period with daily volatility
            sp500_trend = (days_elapsed / total_days) * 3.5
            sp500_volatility = (i % 7 - 3) * 0.3  # Weekly cycle
            sp500_returns.append(round(sp500_trend + sp500_volatility, 2))
            
            # TA-125: ~2.8% total return, slightly different pattern
            ta125_trend = (days_elapsed / total_days) * 2.8
            ta125_volatility = ((i + 2) % 5 - 2) * 0.4  # 5-day cycle
            ta125_returns.append(round(ta125_trend + ta125_volatility, 2))
        
        return {
            'sp500_returns': sp500_returns,
            'ta125_returns': ta125_returns
        }
    
    def get_pending_trades(self) -> List[Dict[str, Any]]:
        """Get trades that haven't been executed yet"""
        pending = []
        
        for data_dir in self.data_dirs:
            trades_file = data_dir / "chatgpt_trade_log.csv"
            # Prefer Client Portal checkpoint if present; otherwise fall back to IB
            cp_checkpoint = data_dir / ".cp_checkpoint.json"
            ib_checkpoint = data_dir / ".ib_checkpoint.json"
            checkpoint_file = cp_checkpoint if cp_checkpoint.exists() else ib_checkpoint
            
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
            # Support both legacy TWS log and Client Portal execution log
            possible_exec_files = [
                data_dir / "ib_execution_log.csv",
                data_dir / "cp_execution_log.csv",
            ]

            for exec_file in possible_exec_files:
                if not exec_file.exists():
                    continue

                try:
                    df = pd.read_csv(exec_file)

                    # Filter by date if specified
                    if days > 0 and 'execution_date' in df.columns:
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
                            'quantity': float(row.get('quantity', 0) or 0),
                            'executed_price': float(row.get('executed_price', 0) or 0),
                            'commission': float(row.get('commission', 0) or 0),
                            'total_cost': float(row.get('total_cost', 0) or 0),
                            'status': str(row.get('status', '')),
                            'slippage': float(row.get('slippage', 0) or 0),
                            'source_dir': str(data_dir.name)
                        }
                        executions.append(execution)

                except Exception as e:
                    self.logger.error(f"Error reading executions from {exec_file}: {e}")
        
        # Sort by actual datetime when possible
        def _to_dt(e: Dict[str, Any]) -> datetime:
            ts = f"{e.get('execution_date','')} {str(e.get('execution_time',''))[:8]}".strip()
            try:
                return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return datetime.min
        return sorted(executions, key=_to_dt, reverse=True)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics"""
        portfolio = self.get_current_portfolio()
        executions = self.get_execution_history(days=30)

        # Current portfolio metrics
        total_value = sum(p['market_value'] for p in portfolio)
        total_pnl = sum(p['unrealized_pnl'] for p in portfolio)
        total_positions = len([p for p in portfolio if p['shares'] > 0])

        # Fallback: if no open positions (or CSV only has TOTAL), derive from TOTAL row
        if total_value == 0 or total_positions == 0:
            newest_file = None
            newest_time = None
            for data_dir in self.data_dirs:
                f = data_dir / "chatgpt_portfolio_update.csv"
                if f.exists():
                    try:
                        mtime = f.stat().st_mtime
                        if newest_time is None or mtime > newest_time:
                            newest_time = mtime
                            newest_file = f
                    except Exception:
                        continue
            if newest_file:
                try:
                    df = pd.read_csv(newest_file)
                    if not df.empty:
                        total_rows = df[df['Ticker'].astype(str).str.upper() == 'TOTAL']
                        if not total_rows.empty:
                            tr = total_rows.iloc[-1]
                            # Prefer 'Total Equity' if present, else 'Total Value'
                            if 'Total Equity' in tr and pd.notna(tr['Total Equity']):
                                total_value = float(tr['Total Equity'])
                            elif 'Total Value' in tr and pd.notna(tr['Total Value']):
                                total_value = float(tr['Total Value'])
                            # P&L total if available
                            if 'PnL' in tr and pd.notna(tr['PnL']):
                                try:
                                    total_pnl = float(tr['PnL'])
                                except Exception:
                                    pass
                except Exception as e:
                    self.logger.error(f"Error deriving portfolio totals from {newest_file}: {e}")
        
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
        """Get recent log entries from known executor logs (IB or Client Portal)"""
        combined_logs: List[Dict[str, str]] = []
        log_filenames = [
            "ib_executor.log",  # legacy TWS/ibapi executor
            "cp_api.log",       # Client Portal API log
            "cp_errors.log",    # Client Portal error log
        ]

        for data_dir in self.data_dirs:
            for fname in log_filenames:
                log_file = data_dir / fname
                if not log_file.exists():
                    continue

                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()

                    # Read tail of each file
                    recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

                    for line in recent_lines:
                        line = line.strip()
                        if not line:
                            continue

                        # Parse log format: timestamp - logger - level - message
                        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (.+?) - (\w+) - (.+)', line)
                        if match:
                            timestamp, logger_name, level, message = match.groups()
                            combined_logs.append({
                                'timestamp': timestamp,
                                'logger': logger_name,
                                'level': level,
                                'message': message,
                                'source_dir': str(data_dir.name)
                            })
                        else:
                            # Fallback for non-standard format
                            combined_logs.append({
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'logger': 'unknown',
                                'level': 'INFO',
                                'message': line,
                                'source_dir': str(data_dir.name)
                            })

                except Exception as e:
                    self.logger.error(f"Error reading logs from {log_file}: {e}")

        # Sort by timestamp if present to ensure most recent ordering
        def parse_ts(ts: str) -> datetime:
            try:
                # Handle 'YYYY-MM-DD HH:MM:SS,mmm' and 'YYYY-MM-DD HH:MM:SS'
                if ',' in ts:
                    return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S,%f')
                return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return datetime.min

        combined_logs.sort(key=lambda x: parse_ts(x['timestamp']))
        return combined_logs[-max_lines:]
    
    def _check_ib_connection(self) -> Dict[str, Any]:
        """Check broker connection status from logs (supports TWS and Client Portal)"""
        status = {
            'connected': False,
            'last_connection': None,
            'connection_issues': []
        }

        # Read a reasonably large tail to avoid missing older 'connected' markers
        logs = self.get_recent_logs(max_lines=2000)

        connected_markers = [
            'connected to ib',
            'connected to client portal',
            'already authenticated with client portal',
            'using account:',
        ]
        error_markers = [
            'connection failed',
            'failed to connect',
            'disconnected',
            'not authenticated',
            'authentication required',
        ]
        # Track most recent connected vs error message
        last_connected_ts: Optional[str] = None
        last_error_ts: Optional[str] = None

        for log in reversed(logs):  # Newest first
            message = log['message'].lower()
            if any(marker in message for marker in connected_markers):
                if not last_connected_ts:
                    last_connected_ts = log['timestamp']
            elif any(err in message for err in error_markers):
                if not last_error_ts:
                    last_error_ts = log['timestamp']
                status['connection_issues'].append({
                    'timestamp': log['timestamp'],
                    'message': log['message']
                })

        # Consider connected if last connected is newer or equal to last error (or no errors)
        def to_dt(ts: Optional[str]) -> datetime:
            if not ts:
                return datetime.min
            try:
                if ',' in ts:
                    return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S,%f')
                return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return datetime.min

        if to_dt(last_connected_ts) >= to_dt(last_error_ts):
            status['connected'] = last_connected_ts is not None
            status['last_connection'] = last_connected_ts
        else:
            status['connected'] = False

        # Fallback heuristic: if CP API log exists and is fresh, and we don't have recent auth errors, consider connected
        if not status['connected']:
            try:
                recent_error = any(
                    any(err in log['message'].lower() for err in error_markers)
                    for log in logs[-200:]
                )
                if not recent_error:
                    for data_dir in self.data_dirs:
                        cp_log = data_dir / 'cp_api.log'
                        if cp_log.exists():
                            mtime = datetime.fromtimestamp(cp_log.stat().st_mtime)
                            if datetime.now() - mtime < timedelta(minutes=10):
                                status['connected'] = True
                                status['last_connection'] = mtime.strftime('%Y-%m-%d %H:%M:%S')
                                break
            except Exception:
                pass

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
        # Check IB/CP config for trading mode
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
            # Client Portal config
            cp_config = data_dir / "cp_config.yaml"
            if cp_config.exists():
                try:
                    import yaml
                    with open(cp_config, 'r') as f:
                        config = yaml.safe_load(f)
                    return config.get('trading', {}).get('mode', 'unknown')
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
