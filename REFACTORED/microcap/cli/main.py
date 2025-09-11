from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict
import time

import pandas as pd

from ..domain.clock import Clock
from ..domain.models import Position, PortfolioSnapshot, Trade, TradeLogEntry
from ..data.prices import FakeProvider, ChainedProvider, trading_day_window
from ..io.portfolio_store import PortfolioStore
from ..io.trade_log_store import TradeLogStore
from ..logging import events


def build_fake_provider() -> FakeProvider:
    # Minimal synthetic OHLCV for tests / offline runs
    # 2 days of bars per ticker
    idx = pd.to_datetime(["2025-01-02", "2025-01-03"])  # arbitrary weekdays
    def frame(o, h, l, c):
        return pd.DataFrame({
            "Open": [o, o], "High": [h, h], "Low": [l, l], "Close": [c, c], "Adj Close": [c, c], "Volume": [1000, 1200]
        }, index=idx)
    frames = {
        "AAPL": frame(100, 105, 95, 102),
        "SPY": frame(500, 505, 495, 502),
    }
    return FakeProvider(frames=frames)


def cmd_update(args: argparse.Namespace) -> int:
    clock = Clock(as_of=date.fromisoformat(args.asof) if args.asof else None)
    store = PortfolioStore(Path(args.file))
    positions, cash = store.load_latest_positions_and_cash()
    if args.starting_cash is not None and (not positions and cash == 0.0):
        cash = float(args.starting_cash)

    provider = build_fake_provider()  # offline deterministic
    s, e = trading_day_window(clock, days=1)
    prices: Dict[str, float] = {}
    for p in positions:
        res = provider.download(p.ticker, s.to_pydatetime(), e.to_pydatetime())
        last = res.df["Close"].iloc[-1] if not res.df.empty else p.buy_price
        prices[p.ticker] = float(last)

    snap = PortfolioSnapshot(date=s.date(), positions=positions, cash=cash)
    store.append_snapshot(snap, prices)
    return 0


def cmd_trade(args: argparse.Namespace) -> int:
    # Append to trade log only; portfolio update handled by update command
    tdate = date.fromisoformat(args.date) if args.date else date.today()
    log = TradeLogStore(Path(args.trade_log))
    reason = args.reason or ("MANUAL " + args.side.upper())
    if args.side.lower() == "buy":
        entry = TradeLogEntry(
            date=tdate, ticker=args.ticker.upper(),
            shares_bought=float(args.shares), buy_price=float(args.price),
            cost_basis=float(args.shares) * float(args.price), pnl=0.0, reason=reason
        )
    else:
        entry = TradeLogEntry(
            date=tdate, ticker=args.ticker.upper(),
            shares_sold=float(args.shares), sell_price=float(args.price),
            cost_basis=0.0, pnl=0.0, reason=reason
        )
    log.append(entry)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="microcap")
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("update", help="Append daily portfolio snapshot")
    u.add_argument("--file", required=True, help="Path to chatgpt_portfolio_update.csv")
    u.add_argument("--asof", help="YYYY-MM-DD override for today's date")
    u.add_argument("--starting-cash", type=float, help="Starting cash if portfolio empty")
    u.set_defaults(func=cmd_update)

    t = sub.add_parser("trade", help="Append a trade log entry")
    t.add_argument("--trade-log", required=True, help="Path to chatgpt_trade_log.csv")
    t.add_argument("--side", choices=["buy","sell"], required=True)
    t.add_argument("--ticker", required=True)
    t.add_argument("--shares", type=float, required=True)
    t.add_argument("--price", type=float, required=True)
    t.add_argument("--date", help="YYYY-MM-DD")
    t.add_argument("--reason", help="Optional reason")
    t.set_defaults(func=cmd_trade)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    start = time.time()
    exec_id = events.startup("microcap.cli", {"cmd": args.cmd})
    events.exec_start(exec_id)
    try:
        rc = args.func(args)
        events.exec_complete(exec_id, (time.time() - start) * 1000.0, {"rc": rc})
        return rc
    except Exception as e:  # pragma: no cover
        events.exec_failed(exec_id, (time.time() - start) * 1000.0, str(e))
        events.pipeline_error("cli failure", e)
        raise


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

