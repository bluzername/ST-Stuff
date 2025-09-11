from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Dict, List


@dataclass
class Position:
    ticker: str
    shares: float
    buy_price: float
    cost_basis: float
    stop_loss: float = 0.0

    def add_shares(self, add_shares: float, price: float) -> None:
        if add_shares <= 0:
            return
        new_cost = self.cost_basis + add_shares * price
        new_shares = self.shares + add_shares
        self.buy_price = new_cost / new_shares if new_shares else 0.0
        self.shares = new_shares
        self.cost_basis = new_cost

    def remove_shares(self, remove_shares: float, price: float) -> float:
        if remove_shares <= 0:
            return 0.0
        remove_shares = min(remove_shares, self.shares)
        realized = remove_shares * (price - self.buy_price)
        self.shares -= remove_shares
        self.cost_basis = self.shares * self.buy_price
        return realized


@dataclass
class Trade:
    date: date
    ticker: str
    side: str  # BUY or SELL
    shares: float
    price: float
    reason: str = ""


@dataclass
class TradeLogEntry:
    date: date
    ticker: str
    shares_bought: float = 0.0
    buy_price: float = 0.0
    shares_sold: float = 0.0
    sell_price: float = 0.0
    cost_basis: float = 0.0
    pnl: float = 0.0
    reason: str = ""


@dataclass
class PortfolioSnapshot:
    date: date
    positions: List[Position] = field(default_factory=list)
    cash: float = 0.0
    total_equity: float = 0.0

    def to_rows(self, prices: Dict[str, float]) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for p in self.positions:
            cur_price = float(prices.get(p.ticker, p.buy_price))
            market_value = p.shares * cur_price
            unrealized = market_value - p.cost_basis
            rows.append({
                "Date": self.date.isoformat(),
                "Ticker": p.ticker,
                "Shares": p.shares,
                "Buy Price": p.buy_price,
                "Cost Basis": p.cost_basis,
                "Current Price": cur_price,
                "Total Value": market_value,
                "PnL": unrealized,
                "Stop Loss": p.stop_loss,
                "Cash Balance": "",
                "Total Equity": "",
                "Action": "HOLD",
            })
        # TOTAL row
        total_positions_value = sum(r["Total Value"] for r in rows)
        total_equity = total_positions_value + self.cash
        rows.append({
            "Date": self.date.isoformat(),
            "Ticker": "TOTAL",
            "Shares": "",
            "Buy Price": "",
            "Cost Basis": "",
            "Current Price": "",
            "Total Value": total_positions_value,
            "PnL": sum(r["PnL"] for r in rows),
            "Stop Loss": "",
            "Cash Balance": self.cash,
            "Total Equity": total_equity,
            "Action": "TOTAL",
        })
        self.total_equity = total_equity
        return rows

