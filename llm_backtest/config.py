from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import os


@dataclass
class SourceConfig:
    # Toggle sources; Wayback is the most generic and robust free option
    use_wayback: bool = True
    use_sec_edgar: bool = True

    # Retrieval limits
    max_docs_per_day: int = 200
    top_k: int = 10


@dataclass
class LLMConfig:
    # If False, no LLM calls are made; harness returns no-trade decisions
    enabled: bool = False
    provider: str = "openrouter"  # via OpenRouter
    model: str = "openai/gpt-4o-mini"  # can be changed to another OpenRouter model
    # Environment variables: OPENAI_API_KEY expected when enabled


@dataclass
class ExecConfig:
    # Execution realism (defaults reasonable for micro/small caps)
    slippage_bps: float = 50.0
    commission_per_share: float = 0.005
    min_commission: float = 1.0
    max_participation_rate: float = 0.10
    tick_size: float = 0.01


@dataclass
class PortfolioRules:
    initial_cash: float = 100_000.0
    max_positions: int = 10
    target_position_pct: float = 0.10  # of current equity per BUY
    min_confidence: float = 0.55       # minimum LLM confidence to act


@dataclass
class BacktestWindow:
    start: datetime
    end: datetime

    @staticmethod
    def from_strings(start: str, end: Optional[str] = None) -> "BacktestWindow":
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end) if end else datetime.now()
        return BacktestWindow(start=s, end=e)


@dataclass
class BacktestConfig:
    data_dir: Path = field(default_factory=lambda: Path("backtests"))
    run_name: str = "run_001"
    timezone: str = "America/New_York"
    window: BacktestWindow = field(default_factory=lambda: BacktestWindow.from_strings("2024-06-01", None))
    cadence: str = "EOD"
    # If provided, limit to these tickers; else strategy/LLM may choose
    universe: List[str] = field(default_factory=list)

    sources: SourceConfig = field(default_factory=SourceConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    exec: ExecConfig = field(default_factory=ExecConfig)
    rules: PortfolioRules = field(default_factory=PortfolioRules)

    def output_dir(self) -> Path:
        return self.data_dir / self.run_name

    @staticmethod
    def defaults(start: str = "2024-06-01", end: Optional[str] = None) -> "BacktestConfig":
        cfg = BacktestConfig()
        cfg.window = BacktestWindow.from_strings(start, end)
        return cfg
