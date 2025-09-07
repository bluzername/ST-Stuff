"""
Execution Logger for Interactive Brokers trades

Logs all actual IB trade executions to CSV for audit trail and analysis.
"""

import csv
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


class ExecutionLogger:
    """Logs IB trade executions to CSV with detailed tracking"""
    
    # CSV columns for execution log
    COLUMNS = [
        'execution_date',      # Date executed
        'execution_time',      # Time executed
        'ib_order_id',        # IB order ID
        'ib_perm_id',         # IB permanent ID
        'ticker',             # Symbol
        'action',             # BUY/SELL
        'quantity',           # Shares
        'order_type',         # MKT/LMT/STP
        'limit_price',        # For limit orders (0 if market)
        'executed_price',     # Actual fill price
        'commission',         # IB commission
        'total_cost',         # Shares * Price + Commission
        'status',             # FILLED/PARTIAL/CANCELLED/PENDING
        'csv_source',         # Which CSV file triggered this
        'csv_row_date',       # Date from original CSV signal
        'csv_row_index',      # Row index in source CSV
        'slippage',           # Executed vs Expected price
        'notes'               # Any errors or additional info
    ]
    
    def __init__(self, log_file: str = "ib_execution_log.csv"):
        self.log_file = Path(log_file)
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        """Create CSV with headers if it doesn't exist"""
        if not self.log_file.exists():
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.COLUMNS)
    
    def log_execution(self, execution_data: Dict[str, Any]) -> None:
        """Log a trade execution to CSV"""
        
        # Ensure all required fields exist
        record = {}
        for col in self.COLUMNS:
            record[col] = execution_data.get(col, "")
        
        # Calculate derived fields
        if record['executed_price'] and record['limit_price']:
            try:
                executed = float(record['executed_price'])
                limit = float(record['limit_price'])
                if limit > 0:  # Avoid division by zero
                    record['slippage'] = round(((executed - limit) / limit) * 100, 4)
            except (ValueError, TypeError):
                record['slippage'] = 0
        
        # Write to CSV
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.COLUMNS)
            writer.writerow(record)
    
    def log_order_placement(self, order_data: Dict[str, Any]) -> None:
        """Log when order is placed (before execution)"""
        execution_data = {
            'execution_date': datetime.now().date().isoformat(),
            'execution_time': datetime.now().time().isoformat(),
            'ib_order_id': order_data.get('order_id', ''),
            'ticker': order_data.get('ticker', ''),
            'action': order_data.get('action', ''),
            'quantity': order_data.get('quantity', 0),
            'order_type': order_data.get('order_type', ''),
            'limit_price': order_data.get('price', 0),
            'status': 'SUBMITTED',
            'csv_source': order_data.get('csv_source', ''),
            'csv_row_date': order_data.get('csv_date', ''),
            'csv_row_index': order_data.get('csv_index', ''),
            'notes': 'Order submitted to IB'
        }
        self.log_execution(execution_data)
    
    def update_execution_status(self, order_id: str, status_data: Dict[str, Any]) -> None:
        """Update existing order with execution details"""
        # Read existing CSV
        if not self.log_file.exists():
            return
            
        df = pd.read_csv(self.log_file)
        
        # Find the order
        mask = df['ib_order_id'] == str(order_id)
        if not mask.any():
            return
        
        # Update the row
        for col, value in status_data.items():
            if col in self.COLUMNS:
                df.loc[mask, col] = value
        
        # Recalculate slippage if we have execution price
        if 'executed_price' in status_data:
            try:
                executed = float(status_data['executed_price'])
                limit_price = df.loc[mask, 'limit_price'].iloc[0]
                if pd.notna(limit_price) and float(limit_price) > 0:
                    limit = float(limit_price)
                    slippage = ((executed - limit) / limit) * 100
                    df.loc[mask, 'slippage'] = round(slippage, 4)
            except (ValueError, TypeError):
                pass
        
        # Save back to CSV
        df.to_csv(self.log_file, index=False)
    
    def get_execution_history(self, days: int = 30) -> pd.DataFrame:
        """Get execution history for analysis"""
        if not self.log_file.exists():
            return pd.DataFrame(columns=self.COLUMNS)
        
        df = pd.read_csv(self.log_file)
        
        # Filter by date if specified
        if days > 0:
            cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=days)
            df['execution_date'] = pd.to_datetime(df['execution_date'])
            df = df[df['execution_date'] >= cutoff_date]
        
        return df
    
    def get_daily_trade_count(self, date: str = None) -> int:
        """Get number of trades executed on a specific date"""
        if not self.log_file.exists():
            return 0
        
        df = pd.read_csv(self.log_file)
        
        if date is None:
            date = datetime.now().date().isoformat()
        
        daily_trades = df[df['execution_date'] == date]
        return len(daily_trades[daily_trades['status'] != 'CANCELLED'])
    
    def get_slippage_stats(self, days: int = 30) -> Dict[str, float]:
        """Calculate slippage statistics"""
        df = self.get_execution_history(days)
        
        if df.empty or 'slippage' not in df.columns:
            return {}
        
        # Only consider filled orders
        filled = df[df['status'] == 'FILLED']
        slippage = pd.to_numeric(filled['slippage'], errors='coerce').dropna()
        
        if slippage.empty:
            return {}
        
        return {
            'mean_slippage_pct': round(slippage.mean(), 4),
            'median_slippage_pct': round(slippage.median(), 4),
            'max_slippage_pct': round(slippage.max(), 4),
            'min_slippage_pct': round(slippage.min(), 4),
            'std_slippage_pct': round(slippage.std(), 4),
            'total_trades': len(slippage)
        }