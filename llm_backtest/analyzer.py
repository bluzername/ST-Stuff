cd /Users/xx/Documents/EB/Projects/ST-Stuff/ST-Stuff
cat > llm_backtest/analyzer.py << 'EOF'
"""Backtest analysis and comparison utilities."""

from __future__ import annotations
import json
import csv
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass
import argparse

@dataclass
class BacktestMetrics:
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    
    @classmethod
    def from_equity_curve(cls, equity_file: Path) -> "BacktestMetrics":
        """Calculate metrics from equity curve CSV."""
        dates = []
        equities = []
        
        try:
            with open(equity_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dates.append(row['date'])
                    equities.append(float(row['equity']))
        except Exception as e:
            print(f"Error reading equity curve: {e}")
            return cls(0, 0, 0, 0, 0, 0, 0)
        
        if not equities:
            return cls(0, 0, 0, 0, 0, 0, 0)
        
        # Calculate returns
        initial_equity = equities[0]
        final_equity = equities[-1]
        total_return = (final_equity - initial_equity) / initial_equity
        
        # Calculate annualized return (assuming ~250 trading days per year)
        days = len(equities)
        if days > 1:
            annualized_return = (1 + total_return) ** (250 / days) - 1
        else:
            annualized_return = 0
        
        # Calculate drawdown
        max_drawdown = 0
        peak = equities[0]
        for equity in equities:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        return cls(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=0,  # Would need daily returns to calculate
            sharpe_ratio=0,  # Would need risk-free rate
            max_drawdown=max_drawdown,
            total_trades=0,  # Would need to read fills.csv
            win_rate=0  # Would need to read fills.csv
        )

def compare_backtests(run1: str, run2: str, base_dir: Path = Path("backtests")) -> None:
    """Compare two backtest runs."""
    
    run1_dir = base_dir / run1
    run2_dir = base_dir / run2
    
    if not run1_dir.exists():
        print(f"❌ Run '{run1}' not found in {base_dir}")
        return
    if not run2_dir.exists():
        print(f"❌ Run '{run2}' not found in {base_dir}")
        return
    
    print(f"\n🔍 BACKTEST COMPARISON: {run1} vs {run2}")
    print("=" * 60)
    
    # Check equity curves
    eq1 = run1_dir / "equity_curve.csv"
    eq2 = run2_dir / "equity_curve.csv"
    
    if eq1.exists() and eq2.exists():
        metrics1 = BacktestMetrics.from_equity_curve(eq1)
        metrics2 = BacktestMetrics.from_equity_curve(eq2)
        
        print("
📊 PERFORMANCE SUMMARY:"        print(".2f"        print(".2f"        
        if metrics1.annualized_return != metrics2.annualized_return:
            winner = run1 if metrics1.annualized_return > metrics2.annualized_return else run2
            print(f"🏆 Better performer: {winner}")
    else:
        print("❌ Missing equity curve files")
    
    # Check trading activity
    fills1 = run1_dir / "fills.csv"
    fills2 = run2_dir / "fills.csv"
    
    trades1 = sum(1 for _ in csv.DictReader(open(fills1))) if fills1.exists() else 0
    trades2 = sum(1 for _ in csv.DictReader(open(fills2))) if fills2.exists() else 0
    
    print("
📈 TRADING ACTIVITY:"    print(f"{run1}: {trades1} trades")
    print(f"{run2}: {trades2} trades")
    
    # Configuration comparison would go here if we had config files
    print("
⚙️  CONFIGURATION:"    print("   - Configuration comparison not available (no config files saved)")
    print("   - Would show differences in tickers, dates, LLM settings, etc.")

def main():
    parser = argparse.ArgumentParser(description="Compare LLM backtest results")
    parser.add_argument("run1", help="First backtest run name")
    parser.add_argument("run2", help="Second backtest run name")
    parser.add_argument("--base-dir", default="backtests", help="Base directory for backtests")
    
    args = parser.parse_args()
    compare_backtests(args.run1, args.run2, Path(args.base_dir))

if __name__ == "__main__":
    main()
EOF