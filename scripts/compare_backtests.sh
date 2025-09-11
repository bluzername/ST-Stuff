cd /Users/xx/Documents/EB/Projects/ST-Stuff/ST-Stuff
cat > scripts/compare_backtests.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

# Backtest comparison script
# Usage: bash scripts/compare_backtests.sh run1 run2

if [ $# -ne 2 ]; then
    echo "Usage: $0 <run1> <run2>"
    echo "Example: $0 conservative aggressive"
    exit 1
fi

RUN1="$1"
RUN2="$2"

# Change to project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

if command -v uv >/dev/null 2>&1; then
  uv run -- python -m llm_backtest.analyzer compare "$RUN1" "$RUN2"
elif [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m llm_backtest.analyzer compare "$RUN1" "$RUN2"
else
  python -m llm_backtest.analyzer compare "$RUN1" "$RUN2"
fi
EOF

chmod +x scripts/compare_backtests.sh