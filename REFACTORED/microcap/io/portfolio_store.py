from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd

from ..domain.models import Position, PortfolioSnapshot


PORTFOLIO_COLUMNS = [
    "Date","Ticker","Shares","Buy Price","Cost Basis","Current Price",
    "Total Value","PnL","Stop Loss","Cash Balance","Total Equity","Action"
]


@dataclass
class PortfolioStore:
    csv_path: Path

    def ensure_file(self) -> None:
        if not self.csv_path.exists():
            df = pd.DataFrame(columns=PORTFOLIO_COLUMNS)
            df.to_csv(self.csv_path, index=False)

    def load_latest_positions_and_cash(self) -> Tuple[List[Position], float]:
        self.ensure_file()
        df = pd.read_csv(self.csv_path)
        if df.empty:
            return [], 0.0
        # Keep only latest non-TOTAL rows by Date
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        non_total = df[df["Ticker"] != "TOTAL"].copy()
        if non_total.empty:
            # No positions, try last cash from TOTAL
            totals = df[df["Ticker"] == "TOTAL"].copy()
            totals["Date"] = pd.to_datetime(totals["Date"], errors="coerce")
            totals = totals.sort_values("Date")
            last_cash = float(totals.iloc[-1]["Cash Balance"]) if not totals.empty else 0.0
            return [], last_cash

        latest_date = non_total["Date"].max()
        latest_rows = non_total[non_total["Date"] == latest_date]
        positions: List[Position] = []
        for _, row in latest_rows.iterrows():
            if str(row.get("Ticker","")) == "TOTAL":
                continue
            shares = float(row.get("Shares", 0) or 0)
            if shares <= 0:
                continue
            positions.append(Position(
                ticker=str(row["Ticker"]).upper(),
                shares=shares,
                buy_price=float(row.get("Buy Price", 0) or 0),
                cost_basis=float(row.get("Cost Basis", 0) or 0),
                stop_loss=float(row.get("Stop Loss", 0) or 0),
            ))

        # last cash from TOTAL row
        totals = df[df["Ticker"] == "TOTAL"].copy()
        totals["Date"] = pd.to_datetime(totals["Date"], errors="coerce")
        totals = totals.sort_values("Date")
        last_cash = float(totals.iloc[-1]["Cash Balance"]) if not totals.empty else 0.0
        return positions, last_cash

    def append_snapshot(self, snapshot: PortfolioSnapshot, prices: Dict[str, float]) -> None:
        self.ensure_file()
        rows = snapshot.to_rows(prices)
        df_new = pd.DataFrame(rows, columns=PORTFOLIO_COLUMNS)
        if self.csv_path.exists():
            try:
                df_old = pd.read_csv(self.csv_path)
            except Exception:
                df_old = pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        else:
            df_old = pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        df = pd.concat([df_old, df_new], ignore_index=True)
        df.to_csv(self.csv_path, index=False)

