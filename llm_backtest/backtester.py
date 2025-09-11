from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Iterable
import csv
import math

import pandas as pd

from .config import BacktestConfig
from .docstore import DocStore
from .retriever import retrieve
from .harness import LLMClient, decide_trades

# Reuse price access and slippage/fees from trading_script
from trading_script import download_price_data, set_backtest_config


def _trading_days(start: datetime, end: datetime) -> List[datetime]:
    """Return list of trading dates (date-only) between start and end inclusive.
    Uses business days (Mon–Fri). Holiday handling can be added later if needed.
    """
    days: List[datetime] = []
    day = datetime(start.year, start.month, start.day)
    end_d = datetime(end.year, end.month, end.day)
    one = timedelta(days=1)
    while day <= end_d:
        if day.weekday() < 5:  # Mon–Fri
            days.append(day)
        day += one
    return days


@dataclass
class Position:
    shares: float
    avg_price: float


class Backtester:
    def __init__(self, cfg: BacktestConfig, out_dir: Path, docstore: DocStore,
                 universe: List[str]):
        self.cfg = cfg
        self.out = out_dir
        self.docstore = docstore
        self.universe = [t.upper() for t in universe]
        self.client = LLMClient(cfg.llm)

        # State
        self.cash: float = cfg.rules.initial_cash
        self.positions: Dict[str, Position] = {}

        # Outputs
        self.orders_file = self.out / "orders.csv"
        self.fills_file = self.out / "fills.csv"
        self.equity_file = self.out / "equity_curve.csv"
        self.decisions_log = self.out / "decisions.jsonl"
        self.retrievals_log = self.out / "retrievals.jsonl"

        # Apply execution realism to trading_script
        set_backtest_config(
            slippage_bps=cfg.exec.slippage_bps,
            commission_per_share=cfg.exec.commission_per_share,
            min_commission=cfg.exec.min_commission,
            max_participation_rate=cfg.exec.max_participation_rate,
            tick_size=cfg.exec.tick_size,
        )

        # Init output files
        if not self.orders_file.exists():
            with open(self.orders_file, "w", newline="") as fh:
                csv.writer(fh).writerow([
                    "signal_date", "exec_date", "ticker", "side", "qty", "order_type", "note"
                ])
        if not self.fills_file.exists():
            with open(self.fills_file, "w", newline="") as fh:
                csv.writer(fh).writerow([
                    "exec_date", "ticker", "side", "qty", "price", "commission", "notional"
                ])
        if not self.equity_file.exists():
            with open(self.equity_file, "w", newline="") as fh:
                csv.writer(fh).writerow([
                    "date", "cash", "positions_value", "equity"
                ])

    def _append_decision(self, as_of: datetime, payload: dict) -> None:
        with open(self.decisions_log, "a", encoding="utf-8") as f:
            import json
            payload = {**payload, "as_of": as_of.isoformat()}
            f.write(json.dumps(payload) + "\n")

    def _append_retrieval(self, as_of: datetime, query: str, doc_id: str, url: str, published_at: str, score: float, source: str) -> None:
        with open(self.retrievals_log, "a", encoding="utf-8") as f:
            import json
            f.write(json.dumps({
                "as_of": as_of.isoformat(),
                "query": query,
                "doc_id": doc_id,
                "url": url,
                "published_at": published_at,
                "score": score,
                "source": source,
            }) + "\n")

    def _log_order(self, signal_date: datetime, exec_date: datetime, ticker: str, side: str, qty: float, order_type: str, note: str) -> None:
        with open(self.orders_file, "a", newline="") as fh:
            csv.writer(fh).writerow([
                signal_date.date().isoformat(), exec_date.date().isoformat(), ticker, side, int(qty), order_type, note
            ])

    def _log_fill(self, exec_date: datetime, ticker: str, side: str, qty: float, price: float, commission: float) -> None:
        with open(self.fills_file, "a", newline="") as fh:
            notional = round(price * qty, 2)
            csv.writer(fh).writerow([
                exec_date.date().isoformat(), ticker, side, int(qty), round(price, 4), round(commission, 2), notional
            ])

    def _log_equity(self, date: datetime) -> None:
        # Mark-to-market at close
        positions_value = 0.0
        for t, p in self.positions.items():
            # pull close for this date
            s = pd.Timestamp(date)
            e = s + pd.Timedelta(days=1)
            fetch = download_price_data(t, start=s, end=e, auto_adjust=False, progress=False)
            df = fetch.df
            if df.empty:
                continue
            close = float(df["Close"].iloc[-1])
            positions_value += close * p.shares
        equity = self.cash + positions_value
        with open(self.equity_file, "a", newline="") as fh:
            csv.writer(fh).writerow([
                date.date().isoformat(), round(self.cash, 2), round(positions_value, 2), round(equity, 2)
            ])

    # --- Strategy helpers ---
    def _target_dollar_allocation(self, equity: float) -> float:
        return equity * self.cfg.rules.target_position_pct

    def _current_equity_estimate(self, date: datetime) -> float:
        # quick estimate using last closes; used for sizing only
        positions_value = 0.0
        for t, p in self.positions.items():
            s = pd.Timestamp(date)
            e = s + pd.Timedelta(days=1)
            fetch = download_price_data(t, start=s, end=e, auto_adjust=False, progress=False)
            df = fetch.df
            if df.empty:
                continue
            close = float(df["Close"].iloc[-1])
            positions_value += close * p.shares
        return self.cash + positions_value

    def _place_eod_orders(self, signal_date: datetime, decisions: List, next_open_date: datetime) -> List[Tuple[str, str, float]]:
        """Translate decisions into naive MOO orders for next session.

        Returns list of (ticker, side, qty) orders.
        """
        orders: List[Tuple[str, str, float]] = []
        equity_est = self._current_equity_estimate(signal_date)
        tgt_dollar = self._target_dollar_allocation(equity_est)

        for d in decisions:
            t = d.ticker
            if t not in self.universe:
                continue
            if d.confidence < self.cfg.rules.min_confidence:
                continue
            if d.action == "BUY":
                if t in self.positions:
                    continue
                if len(self.positions) >= self.cfg.rules.max_positions:
                    continue
                # Estimate quantity using last close
                s = pd.Timestamp(signal_date)
                e = s + pd.Timedelta(days=1)
                fetch = download_price_data(t, start=s, end=e, auto_adjust=False, progress=False)
                df = fetch.df
                if df.empty:
                    continue
                ref_px = float(df["Close"].iloc[-1])
                if ref_px <= 0:
                    continue
                qty = max(0, int(tgt_dollar // ref_px))
                if qty <= 0:
                    continue
                orders.append((t, "BUY", float(qty)))
                self._log_order(signal_date, next_open_date, t, "BUY", qty, "MOO", f"conf={d.confidence:.2f}")
            elif d.action == "SELL":
                if t not in self.positions:
                    continue
                qty = float(int(self.positions[t].shares))
                if qty <= 0:
                    continue
                orders.append((t, "SELL", qty))
                self._log_order(signal_date, next_open_date, t, "SELL", qty, "MOO", f"conf={d.confidence:.2f}")
            else:
                continue
        return orders

    def _execute_moo_orders(self, exec_date: datetime, orders: List[Tuple[str, str, float]]) -> None:
        # Use next day [exec, exec+1) to get Open & Volume
        s = pd.Timestamp(exec_date)
        e = s + pd.Timedelta(days=1)
        for t, side, qty in orders:
            fetch = download_price_data(t, start=s, end=e, auto_adjust=False, progress=False)
            df = fetch.df
            if df.empty:
                continue
            o = float(df["Open"].iloc[-1]) if "Open" in df else float(df["Close"].iloc[-1])
            v = float(df["Volume"].iloc[-1]) if "Volume" in df else float("nan")

            # slippage & participation – mirror trading_script helpers:
            from trading_script import _apply_slippage as apply_slip, _cap_by_volume as cap_vol, _calc_commission as calc_comm
            px = apply_slip(o, side.lower())
            # Volume cap
            fillable = float(min(int(qty), int(cap_vol(qty, v))))
            if side == "BUY":
                # Cash cap — approximate using trading_script helper
                from trading_script import _cap_by_cash_for_buy as cap_cash
                fillable = float(int(cap_cash(self.cash, px, fillable)))
            if fillable <= 0:
                continue
            fees = float(calc_comm(fillable))
            notional = px * fillable
            if side == "BUY":
                total = notional + fees
                if total > self.cash + 1e-9:
                    # reduce to affordable
                    affordable = max(0, int((self.cash - fees) // px))
                    fillable = float(affordable)
                    if fillable <= 0:
                        continue
                    fees = float(calc_comm(fillable))
                    notional = px * fillable
                    total = notional + fees
                self.cash -= total
                # Update/insert position
                if t not in self.positions:
                    self.positions[t] = Position(shares=fillable, avg_price=px)
                else:
                    p = self.positions[t]
                    new_shares = p.shares + fillable
                    new_cost = p.avg_price * p.shares + notional
                    p.shares = new_shares
                    p.avg_price = new_cost / new_shares if new_shares else 0.0
                self._log_fill(exec_date, t, side, fillable, px, fees)
            else:  # SELL
                proceeds = notional - fees
                self.cash += proceeds
                # Reduce/close position
                if t in self.positions:
                    p = self.positions[t]
                    p.shares -= fillable
                    if p.shares <= 0:
                        del self.positions[t]
                self._log_fill(exec_date, t, side, fillable, px, fees)

    def run(self) -> None:
        # Iterate EOD decisions at D -> execute at D+1 open -> log equity at D+1 close
        days = _trading_days(self.cfg.window.start, self.cfg.window.end)
        if not days:
            return
        for i, day in enumerate(days[:-1]):  # last day has no next open/close
            as_of = datetime(day.year, day.month, day.day, 16, 0, 0)
            next_day = days[i + 1]

            # Retrieve docs available as_of
            asof_docs = list(self.docstore.query_asof(as_of, limit=self.cfg.sources.max_docs_per_day))
            # Build per-ticker queries
            queries = [f"{t} 10-Q 10-K press release clinical trial guidance" for t in self.universe]
            retrieved_all = []
            for q in queries:
                rs = retrieve(asof_docs, q, as_of, top_k=self.cfg.sources.top_k)
                for r in rs:
                    self._append_retrieval(as_of, q, r.doc.id, r.doc.url, r.doc.published_at, r.score, r.doc.source)
                retrieved_all.extend(rs)

            decisions = decide_trades(self.client, as_of, self.universe, retrieved_all, docstore=self.docstore, max_rounds=2)
            # Log decisions (raw)
            for d in decisions:
                self._append_decision(as_of, {
                    "ticker": d.ticker, "action": d.action, "confidence": d.confidence,
                    "citations": d.citations, "rationale": d.rationale
                })

            # Create MOO orders for next session
            orders = self._place_eod_orders(as_of, decisions, next_day)
            # Execute at next open
            self._execute_moo_orders(next_day, orders)
            # Mark to market at next close
            self._log_equity(next_day)

