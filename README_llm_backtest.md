LLM Backtest (Time‑Gated RAG)

What this adds
- A leakage‑resistant backtest harness that only allows documents available at or before the backtest timestamp to influence LLM decisions.
- Sources: SEC EDGAR (search API) and Wayback snapshots (generic URLs). More can be added later.
- Simple retrieval (TF‑IDF‑ish) without heavy deps. LLM is disabled by default.

Key files
- `llm_backtest/docstore.py` — JSONL docstore with time gating
- `llm_backtest/sources/edgar.py` — SEC filings (free API; set `SEC_API_USER_AGENT`)
- `llm_backtest/sources/wayback.py` — Archive.org snapshots
- `llm_backtest/retriever.py` — simple retrieval
- `llm_backtest/harness.py` — LLM interface and decision schema
- `llm_backtest/run.py` — CLI runner (EOD loop)

Usage
1) Install deps: `pip install -r requirements.txt`
2) (Recommended) set SEC UA: `export SEC_API_USER_AGENT="Your Name your@email"`
3) Run a dry‑run backtest (no LLM calls):
   `python -m llm_backtest.run --start 2024-06-01 --run-name run_eod --tickers IWM XBI SPY`
   Outputs under `backtests/run_eod/`:
   - `docstore/docs.jsonl` — cached docs
   - `retrievals.jsonl` — queries + retrieved docs per day
   - `decisions.jsonl` — empty by default (LLM disabled)
   - `orders.csv` — placeholder schema

Enable LLM later
- Wire your provider in `LLMClient.generate()` or set `--enable-llm` and implement the call.
- The harness expects strict JSON with `decisions` (ticker, action, confidence, citations, rationale).

Leakage controls
- Only documents with `published_at <= as_of` are retrieved.
- Wayback snapshots fetch the closest archive before the cutoff.
- EDGAR filings use `filedAt` and date filters.

Notes
- This is a minimal, testable scaffold to incrementally add sources and decision logic.
- Intraday is out of scope; cadence is EOD by design.

