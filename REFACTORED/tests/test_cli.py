import unittest
from pathlib import Path
from datetime import date
import tempfile
import pandas as pd

from REFACTORED.microcap.cli.main import main as cli_main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.portfolio_csv = Path(self.tmpdir.name) / "chatgpt_portfolio_update.csv"
        self.trade_csv = Path(self.tmpdir.name) / "chatgpt_trade_log.csv"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_trade_and_update_flow(self):
        # Append a BUY to trade log
        rc = cli_main([
            "trade", "--trade-log", str(self.trade_csv), "--side", "buy", "--ticker", "AAPL",
            "--shares", "5", "--price", "100", "--date", "2025-01-03", "--reason", "UNITTEST"
        ])
        self.assertEqual(rc, 0)
        df_trade = pd.read_csv(self.trade_csv)
        self.assertEqual(len(df_trade), 1)

        # Run update with starting cash (portfolio empty -> cash set)
        rc = cli_main([
            "update", "--file", str(self.portfolio_csv), "--asof", "2025-01-03", "--starting-cash", "1000"
        ])
        self.assertEqual(rc, 0)
        df = pd.read_csv(self.portfolio_csv)
        self.assertGreater(len(df), 0)
        self.assertIn("TOTAL", set(df["Ticker"]))


if __name__ == '__main__':
    unittest.main()

