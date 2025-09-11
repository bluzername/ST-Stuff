Refactored Trading Pipeline (Safe Sandbox)

This directory contains a modular refactor of the ChatGPT Micro‑Cap pipeline.

Principles:
- Do not modify original files; everything lives under REFACTORED/.
- Pure, testable core logic (no prints, no input) with thin CLIs.
- Deterministic unit/integration tests using a fake price provider (no network).

Layout:
- microcap/
  - domain/: dataclasses and pure portfolio math
  - data/: price providers + weekend windowing
  - io/: CSV stores for portfolio and trades (same schemas)
  - reports/: metrics (returns, drawdown)
  - logging/: wrapper around root pipeline_logger (fallback to stdlib)
  - brokers/: abstract gateway + (stub) CP adapter
  - cli/: argparse commands

Running tests:
- python -m REFACTORED.tests.run_tests

Notes:
- Tests rely on FakePriceProvider and local fixtures to avoid network access.
- CSV column names are preserved for compatibility.

