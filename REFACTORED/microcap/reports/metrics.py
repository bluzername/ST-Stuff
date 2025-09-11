from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
import pandas as pd
import numpy as np


def max_drawdown(equity_series: pd.Series) -> Dict[str, Any]:
    if equity_series.empty:
        return {"max_drawdown": 0.0, "date": None}
    equity = equity_series.astype(float).sort_index()
    run_max = equity.cummax()
    dd = (equity / run_max) - 1.0
    return {"max_drawdown": float(dd.min()), "date": dd.idxmin()}


def daily_returns(equity_series: pd.Series) -> pd.Series:
    return equity_series.astype(float).sort_index().pct_change().dropna()


def summary_stats(equity_series: pd.Series) -> Dict[str, Any]:
    r = daily_returns(equity_series)
    if r.empty:
        return {
            "days": 0,
            "avg_daily": 0.0,
            "vol_daily": 0.0,
            "sharpe_daily": 0.0,
        }
    avg = float(r.mean())
    vol = float(r.std(ddof=1)) if len(r) > 1 else 0.0
    sharpe = (avg / vol) if vol else 0.0
    return {
        "days": int(len(r)),
        "avg_daily": avg,
        "vol_daily": vol,
        "sharpe_daily": sharpe,
    }

