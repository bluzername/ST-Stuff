"""LLM backtesting utilities (time-gated RAG + EOD loop).

Phases implemented:
- DocStore with time gating
- Wayback + SEC EDGAR adapters (best-effort, free-only)
- Simple retrieval (keyword/TF scoring)
- LLM harness interface (pluggable)
- CLI runner for EOD backtests
"""

__all__ = [
    "config",
    "docstore",
    "retriever",
    "harness",
]

__version__ = "0.1.0"

cd /Users/xx/Documents/EB/Projects/ST-Stuff/ST-Stuff
# Add "analyzer" to the __all__ list
sed -i '' 's/"harness"/"harness", "analyzer"/' llm_backtest/__init__.py

