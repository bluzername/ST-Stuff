"""
CSV Trade Monitor

Monitors CSV files from trading_script.py and detects new trades to execute.
Maintains checkpoint to avoid processing same trades multiple times.
"""

import json
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging


class CSVTradeMonitor:
    """Monitors CSV files for new trading signals"""
    
    def __init__(self, data_dir: str = "../Start Your Own", checkpoint_file: str = ".ib_checkpoint.json"):
        self.data_dir = Path(data_dir)
        # Use checkpoint inside data_dir when a bare filename is provided
        cf = Path(checkpoint_file)
        if cf.is_absolute() or str(cf.parent) not in (".", ""):
            self.checkpoint_file = cf
        else:
            self.checkpoint_file = self.data_dir / cf.name
        
        # CSV file paths
        self.portfolio_csv = self.data_dir / "chatgpt_portfolio_update.csv"
        self.trade_log_csv = self.data_dir / "chatgpt_trade_log.csv"
        
        # Setup logging first
        self.logger = logging.getLogger(__name__)
        
        # Load checkpoint
        self.checkpoint = self._load_checkpoint()
    
    def _load_checkpoint(self) -> Dict[str, Any]:
        """Load processing checkpoint"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.logger.warning(f"Could not load checkpoint {self.checkpoint_file}")
        
        return {
            'last_trade_log_index': -1,
            'last_portfolio_date': None,
            'processed_orders': []  # List of order IDs already processed
        }
    
    def _save_checkpoint(self) -> None:
        """Save processing checkpoint"""
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.checkpoint, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")
    
    def detect_trades_from_log(self) -> List[Dict[str, Any]]:
        """
        Parse trade_log.csv for explicit buy/sell records
        
        Returns list of trade dictionaries:
        {
            'action': 'BUY' or 'SELL',
            'ticker': 'SYMBOL',
            'quantity': float,
            'price': float,
            'order_type': 'LMT' or 'MKT',
            'source': 'trade_log',
            'csv_date': 'YYYY-MM-DD',
            'csv_index': int,
            'reason': 'Original reason from CSV',
            'stop_loss': float (for buys)
        }
        """
        trades = []
        
        self.logger.info(f"Scanning trade log CSV: {self.trade_log_csv}")
        
        if not self.trade_log_csv.exists():
            self.logger.warning(f"Trade log CSV not found: {self.trade_log_csv}")
            return trades
        
        try:
            df = pd.read_csv(self.trade_log_csv, on_bad_lines='skip')
            self.logger.info(f"Successfully loaded trade log with {len(df)} rows")
        except Exception as e:
            self.logger.error(f"Failed to read trade log CSV: {e}")
            return trades
        
        if df.empty:
            return trades
        
        last_index = self.checkpoint.get('last_trade_log_index', -1)
        self.logger.info(f"Checkpoint: last processed index = {last_index}, scanning from row {last_index + 1}")
        
        processed_rows = 0
        skipped_rows = 0
        
        for idx, row in df.iterrows():
            # Skip already processed rows
            if idx <= last_index:
                skipped_rows += 1
                continue
            
            processed_rows += 1
            reason = str(row.get('Reason', ''))
            ticker = str(row.get('Ticker', '')).upper().strip()
            
            self.logger.debug(f"Processing row {idx}: {ticker} - {reason}")
            
            if not ticker or ticker == 'NAN':
                self.logger.debug(f"Skipping row {idx}: invalid ticker '{ticker}'")
                continue
            
            # Detect buy orders
            if 'MANUAL BUY' in reason:
                quantity = self._safe_float(row.get('Shares Bought', 0))
                price = self._safe_float(row.get('Buy Price', 0))
                
                self.logger.debug(f"Found BUY signal: {quantity} {ticker} @ ${price}")
                
                if quantity > 0 and price > 0:
                    # Determine order type from reason
                    order_type = 'MKT' if 'MOO' in reason else 'LMT'
                    
                    trade = {
                        'action': 'BUY',
                        'ticker': ticker,
                        'quantity': quantity,
                        'price': price,
                        'order_type': order_type,
                        'source': 'trade_log',
                        'csv_date': str(row.get('Date', '')),
                        'csv_index': idx,
                        'reason': reason,
                        'stop_loss': 0  # Not in trade log
                    }
                    trades.append(trade)
                    self.logger.info(f"Added BUY trade: {quantity} {ticker} @ ${price:.2f} ({order_type}) from row {idx}")
                else:
                    self.logger.warning(f"Invalid BUY data at row {idx}: quantity={quantity}, price={price}")  
            
            # Detect sell orders
            elif 'MANUAL SELL' in reason or 'SELL - Stop Loss' in reason:
                quantity = self._safe_float(row.get('Shares Sold', 0))
                price = self._safe_float(row.get('Sell Price', 0))
                
                self.logger.debug(f"Found SELL signal: {quantity} {ticker} @ ${price}")
                
                if quantity > 0 and price > 0:
                    order_type = 'MKT' if 'Stop Loss' in reason else 'LMT'
                    
                    trade = {
                        'action': 'SELL',
                        'ticker': ticker,
                        'quantity': quantity,
                        'price': price,
                        'order_type': order_type,
                        'source': 'trade_log',
                        'csv_date': str(row.get('Date', '')),
                        'csv_index': idx,
                        'reason': reason,
                        'stop_loss': 0
                    }
                    trades.append(trade)
                    self.logger.info(f"Added SELL trade: {quantity} {ticker} @ ${price:.2f} ({order_type}) from row {idx}")
                else:
                    self.logger.warning(f"Invalid SELL data at row {idx}: quantity={quantity}, price={price}")
            else:
                self.logger.debug(f"Row {idx} not a trade signal: {reason}")
        
        # Update checkpoint with highest processed index
        if trades:
            max_index = max(trade['csv_index'] for trade in trades)
            self.checkpoint['last_trade_log_index'] = max_index
            self._save_checkpoint()
            self.logger.info(f"Updated checkpoint to index {max_index}")
        
        self.logger.info(f"Trade log scan complete: processed {processed_rows} rows, skipped {skipped_rows} rows, found {len(trades)} trades")
        return trades
    
    def detect_trades_from_portfolio_changes(self) -> List[Dict[str, Any]]:
        """
        Infer trades from portfolio snapshot changes
        Used as backup method if trade log is incomplete
        """
        trades = []
        
        if not self.portfolio_csv.exists():
            self.logger.warning(f"Portfolio CSV not found: {self.portfolio_csv}")
            return trades
        
        try:
            df = pd.read_csv(self.portfolio_csv)
        except Exception as e:
            self.logger.error(f"Failed to read portfolio CSV: {e}")
            return trades
        
        if df.empty:
            return trades
        
        # Filter out TOTAL rows and get unique dates
        holdings_df = df[df['Ticker'] != 'TOTAL'].copy()
        if holdings_df.empty:
            return trades
        
        # Convert date column
        holdings_df['Date'] = pd.to_datetime(holdings_df['Date'], errors='coerce')
        holdings_df = holdings_df.dropna(subset=['Date']).sort_values('Date')
        
        unique_dates = holdings_df['Date'].dt.date.unique()
        if len(unique_dates) < 2:
            return trades  # Need at least 2 dates to compare
        
        # Get last processed date
        last_date = self.checkpoint.get('last_portfolio_date')
        if last_date:
            last_date = pd.to_datetime(last_date).date()
            # Only process dates after last processed
            unique_dates = [d for d in unique_dates if d > last_date]
        
        # Compare consecutive dates
        for i, current_date in enumerate(unique_dates):
            if i == 0 and last_date is None:
                # Skip first date if no previous checkpoint
                continue
            
            prev_date = unique_dates[i-1] if i > 0 else last_date
            if prev_date is None:
                continue
            
            current_holdings = self._get_holdings_for_date(holdings_df, current_date)
            prev_holdings = self._get_holdings_for_date(holdings_df, prev_date)
            
            # Compare holdings
            inferred_trades = self._infer_trades_from_holdings_change(
                prev_holdings, current_holdings, current_date
            )
            trades.extend(inferred_trades)
        
        # Update checkpoint
        if len(unique_dates) > 0:
            self.checkpoint['last_portfolio_date'] = str(max(unique_dates))
            self._save_checkpoint()
        
        return trades
    
    def _get_holdings_for_date(self, df: pd.DataFrame, target_date: date) -> Dict[str, Dict[str, float]]:
        """Get holdings for a specific date"""
        date_mask = df['Date'].dt.date == target_date
        date_df = df[date_mask]
        
        holdings = {}
        for _, row in date_df.iterrows():
            ticker = str(row.get('Ticker', '')).upper().strip()
            if ticker and ticker != 'NAN':
                holdings[ticker] = {
                    'shares': self._safe_float(row.get('Shares', 0)),
                    'buy_price': self._safe_float(row.get('Buy Price', 0)),
                    'stop_loss': self._safe_float(row.get('Stop Loss', 0))
                }
        
        return holdings
    
    def _infer_trades_from_holdings_change(self, prev_holdings: Dict, current_holdings: Dict, date: date) -> List[Dict[str, Any]]:
        """Infer what trades occurred between two portfolio snapshots"""
        trades = []
        
        all_tickers = set(prev_holdings.keys()) | set(current_holdings.keys())
        
        for ticker in all_tickers:
            prev_shares = prev_holdings.get(ticker, {}).get('shares', 0)
            current_shares = current_holdings.get(ticker, {}).get('shares', 0)
            
            shares_change = current_shares - prev_shares
            
            if abs(shares_change) < 0.01:  # No significant change
                continue
            
            if shares_change > 0:
                # New position or addition - infer BUY
                current_data = current_holdings[ticker]
                trades.append({
                    'action': 'BUY',
                    'ticker': ticker,
                    'quantity': shares_change,
                    'price': current_data.get('buy_price', 0),
                    'order_type': 'LMT',  # Assume limit order
                    'source': 'portfolio_inference',
                    'csv_date': str(date),
                    'csv_index': -1,  # No specific row
                    'reason': 'Inferred from portfolio change',
                    'stop_loss': current_data.get('stop_loss', 0)
                })
            
            else:
                # Reduction or exit - infer SELL
                prev_data = prev_holdings[ticker]
                trades.append({
                    'action': 'SELL',
                    'ticker': ticker,
                    'quantity': abs(shares_change),
                    'price': prev_data.get('buy_price', 0),  # Estimate
                    'order_type': 'LMT',
                    'source': 'portfolio_inference',
                    'csv_date': str(date),
                    'csv_index': -1,
                    'reason': 'Inferred from portfolio change',
                    'stop_loss': 0
                })
        
        return trades
    
    def get_all_pending_trades(self) -> List[Dict[str, Any]]:
        """Get all unprocessed trades from both sources"""
        trades = []
        
        # Primary source: explicit trade log
        log_trades = self.detect_trades_from_log()
        trades.extend(log_trades)
        
        # Backup source: portfolio changes (if no log trades found)
        if not log_trades:
            portfolio_trades = self.detect_trades_from_portfolio_changes()
            trades.extend(portfolio_trades)
        
        # Remove duplicates and filter already processed
        trades = self._deduplicate_trades(trades)
        
        self.logger.info(f"Found {len(trades)} pending trades")
        return trades
    
    def _deduplicate_trades(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate trades based on ticker, action, and date"""
        seen = set()
        unique_trades = []
        
        for trade in trades:
            key = (trade['ticker'], trade['action'], trade['csv_date'], trade['quantity'])
            if key not in seen:
                seen.add(key)
                unique_trades.append(trade)
        
        return unique_trades
    
    def mark_trade_processed(self, trade: Dict[str, Any], order_id: str) -> None:
        """Mark a trade as processed to avoid reprocessing"""
        processed_entry = {
            'ticker': trade['ticker'],
            'action': trade['action'],
            'csv_date': trade['csv_date'],
            'csv_index': trade['csv_index'],
            'order_id': order_id,
            'processed_at': datetime.now().isoformat()
        }
        
        self.checkpoint.setdefault('processed_orders', []).append(processed_entry)
        self._save_checkpoint()
    
    def is_trade_already_processed(self, trade: Dict[str, Any]) -> bool:
        """Check if trade was already processed"""
        processed_orders = self.checkpoint.get('processed_orders', [])
        
        for processed in processed_orders:
            if (processed.get('ticker') == trade['ticker'] and
                processed.get('action') == trade['action'] and
                processed.get('csv_date') == trade['csv_date'] and
                processed.get('csv_index') == trade['csv_index']):
                return True
        
        return False
    
    @staticmethod
    def _safe_float(value: Any) -> float:
        """Safely convert value to float"""
        try:
            if pd.isna(value) or value == '':
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0
