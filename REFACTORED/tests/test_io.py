import unittest
from pathlib import Path
from datetime import date
import tempfile
import pandas as pd

from REFACTORED.microcap.domain.models import Position, PortfolioSnapshot
from REFACTORED.microcap.io.portfolio_store import PortfolioStore
from REFACTORED.microcap.io.trade_log_store import TradeLogStore
from REFACTORED.microcap.domain.models import TradeLogEntry


class TestIOStores(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.portfolio_csv = Path(self.tmpdir.name) / "chatgpt_portfolio_update.csv"
        self.trade_csv = Path(self.tmpdir.name) / "chatgpt_trade_log.csv"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_portfolio_roundtrip(self):
        store = PortfolioStore(self.portfolio_csv)
        positions = [
            Position(ticker="AAPL", shares=10, buy_price=100.0, cost_basis=1000.0, stop_loss=90.0),
        ]
        snap = PortfolioSnapshot(date=date(2025,1,3), positions=positions, cash=500.0)
        prices = {"AAPL": 110.0}
        store.append_snapshot(snap, prices)

        # Load latest
        out_positions, cash = store.load_latest_positions_and_cash()
        self.assertEqual(len(out_positions), 1)
        self.assertEqual(out_positions[0].ticker, "AAPL")
        self.assertAlmostEqual(cash, 500.0)

        # Ensure TOTAL row present
        df = pd.read_csv(self.portfolio_csv)
        self.assertIn("TOTAL", set(df["Ticker"]))

    def test_trade_log_append(self):
        log = TradeLogStore(self.trade_csv)
        entry = TradeLogEntry(date=date(2025,1,3), ticker="AAPL", shares_bought=5, buy_price=100.0, cost_basis=500.0, pnl=0.0, reason="TEST")
        log.append(entry)
        df = pd.read_csv(self.trade_csv)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Ticker"], "AAPL")
        self.assertEqual(df.iloc[0]["Shares Bought"], 5)


if __name__ == '__main__':
    unittest.main()

