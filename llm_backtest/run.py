from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import argparse
import csv
import json
import os

from .config import BacktestConfig
from .docstore import DocStore
from .sources.edgar import fetch_filings_for_ticker
from .backtester import Backtester


def _ensure_dirs(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "docstore").mkdir(parents=True, exist_ok=True)


def _load_universe(cfg: BacktestConfig) -> List[str]:
    if cfg.universe:
        return [t.upper() for t in cfg.universe]
    # Fallback: try to read tickers from portfolio CSV if present
    candidates: List[str] = []
    default_path = Path("Scripts and CSV Files/chatgpt_portfolio_update.csv")
    if default_path.exists():
        import pandas as pd
        try:
            df = pd.read_csv(default_path)
            tickers = df[df["Ticker"] != "TOTAL"]["Ticker"].dropna().unique().tolist()
            candidates = [str(t).upper() for t in tickers if str(t).strip()]
        except Exception:
            pass
    # If still empty, use benchmarks default
    return list(dict.fromkeys(candidates or ["SPY", "IWM", "XBI"]))


def run_backtest(cfg: BacktestConfig) -> None:
    out = cfg.output_dir()
    _ensure_dirs(out)
    docstore = DocStore(out / "docstore")

    # Prepare outputs
    orders_csv = out / "orders.csv"

    universe = _load_universe(cfg)
    # Best-effort ingestion before loop (SEC filings per ticker over the whole window)
    if cfg.sources.use_sec_edgar:
        cache_dir = out / "cache"
        for t in universe:
            try:
                docs = fetch_filings_for_ticker(t, cfg.window.start, cfg.window.end, cache_dir)
                if docs:
                    docstore.add_many(docs)
            except Exception:
                continue

    # End-to-end backtest
    engine = Backtester(cfg, out, docstore, universe)
    engine.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM EOD backtest with time-gated retrieval")
    # Window & naming
    parser.add_argument("--start", required=False, default="2024-06-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=False, default=None, help="End date (YYYY-MM-DD, defaults to today)")
    parser.add_argument("--run-name", required=False, default="run_001", help="Output folder name under backtests/")
    # Universe & LLM
    parser.add_argument("--tickers", nargs="*", default=[], help="Universe tickers (space-separated)")
    parser.add_argument("--enable-llm", action="store_true", help="Enable OpenRouter LLM decisions")
    parser.add_argument("--model", default=None, help="OpenRouter model id (e.g., openai/gpt-4o-mini)")
    # Sources toggles
    parser.add_argument("--no-wayback", action="store_true", help="Disable Wayback ingestion")
    parser.add_argument("--no-sec", action="store_true", help="Disable SEC filings ingestion")
    # Execution realism
    parser.add_argument("--slippage-bps", type=float, default=None)
    parser.add_argument("--commission-per-share", type=float, default=None)
    parser.add_argument("--min-commission", type=float, default=None)
    parser.add_argument("--max-participation", type=float, default=None, help="Max participation rate of daily volume (0-1)")
    parser.add_argument("--tick-size", type=float, default=None)
    # Portfolio rules
    parser.add_argument("--initial-cash", type=float, default=None)
    parser.add_argument("--max-positions", type=int, default=None)
    parser.add_argument("--target-pct", type=float, default=None, help="Target allocation per BUY (0-1)")
    parser.add_argument("--min-confidence", type=float, default=None)
    args = parser.parse_args()

    cfg = BacktestConfig.defaults(args.start, args.end)
    cfg.run_name = args.run_name
    cfg.universe = [t.upper() for t in args.tickers]
    cfg.llm.enabled = bool(args.enable_llm)
    if args.model:
        cfg.llm.model = args.model
    # Source toggles
    if args.no_wayback:
        cfg.sources.use_wayback = False
    if args.no_sec:
        cfg.sources.use_sec_edgar = False
    # Exec realism
    if args.slippage_bps is not None:
        cfg.exec.slippage_bps = args.slippage_bps
    if args.commission_per_share is not None:
        cfg.exec.commission_per_share = args.commission_per_share
    if args.min_commission is not None:
        cfg.exec.min_commission = args.min_commission
    if args.max_participation is not None:
        cfg.exec.max_participation_rate = args.max_participation
    if args.tick_size is not None:
        cfg.exec.tick_size = args.tick_size
    # Portfolio rules
    if args.initial_cash is not None:
        cfg.rules.initial_cash = args.initial_cash
    if args.max_positions is not None:
        cfg.rules.max_positions = args.max_positions
    if args.target_pct is not None:
        cfg.rules.target_position_pct = args.target_pct
    if args.min_confidence is not None:
        cfg.rules.min_confidence = args.min_confidence

    run_backtest(cfg)


if __name__ == "__main__":
    main()

cd /Users/xx/Documents/EB/Projects/ST-Stuff/ST-Stuff
# Add configuration saving after line 63 (after engine.run())
sed -i '' '63a\
    # Save configuration for future comparison\
    config_file = out / "config.json"\
    with open(config_file, "w") as f:\
        json.dump({\
            "run_name": cfg.run_name,\
            "start_date": cfg.window.start.isoformat(),\
            "end_date": cfg.window.end.isoformat(),\
            "universe": cfg.universe,\
            "llm_enabled": cfg.llm.enabled,\
            "llm_model": cfg.llm.model,\
            "initial_cash": cfg.rules.initial_cash,\
            "max_positions": cfg.rules.max_positions,\
            "target_position_pct": cfg.rules.target_position_pct,\
            "min_confidence": cfg.rules.min_confidence,\
            "slippage_bps": cfg.exec.slippage_bps,\
            "commission_per_share": cfg.exec.commission_per_share,\
        }, f, indent=2)\
' llm_backtest/run.py