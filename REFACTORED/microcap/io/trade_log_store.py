from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List
import pandas as pd

from ..domain.models import TradeLogEntry


TRADE_LOG_COLUMNS = [
    "Date","Ticker","Shares Bought","Buy Price","Shares Sold","Sell Price",
    "Cost Basis","PnL","Reason"
]


@dataclass
class TradeLogStore:
    csv_path: Path

    def ensure_file(self) -> None:
        if not self.csv_path.exists():
            df = pd.DataFrame(columns=TRADE_LOG_COLUMNS)
            df.to_csv(self.csv_path, index=False)

    def append(self, entry: TradeLogEntry) -> None:
        self.ensure_file()
        row = {
            "Date": entry.date.isoformat(),
            "Ticker": entry.ticker,
            "Shares Bought": entry.shares_bought or "",
            "Buy Price": entry.buy_price or "",
            "Shares Sold": entry.shares_sold or "",
            "Sell Price": entry.sell_price or "",
            "Cost Basis": entry.cost_basis,
            "PnL": entry.pnl,
            "Reason": entry.reason,
        }
        try:
            df_old = pd.read_csv(self.csv_path)
        except Exception:
            df_old = pd.DataFrame(columns=TRADE_LOG_COLUMNS)
        df_new = pd.DataFrame([row], columns=TRADE_LOG_COLUMNS)
        df = pd.concat([df_old, df_new], ignore_index=True)
        df.to_csv(self.csv_path, index=False)

