#!/usr/bin/env bash
set -euo pipefail

# One-command backtest runner
# Usage: bash scripts/backtest.sh --start 2024-06-01 --tickers IWM XBI SPY --enable-llm

# Change to project root directory to ensure module imports work correctly
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

if command -v uv >/dev/null 2>&1; then
  uv run -- python -m llm_backtest.run "$@"
elif [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m llm_backtest.run "$@"
else
  python -m llm_backtest.run "$@"
fi
