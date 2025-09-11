import unittest
from datetime import date
import pandas as pd

from REFACTORED.microcap.domain.clock import Clock
from REFACTORED.microcap.data.prices import FakeProvider, trading_day_window


class TestPrices(unittest.TestCase):
    def test_trading_day_window_weekend(self):
        # Sunday -> previous Friday
        clock = Clock(as_of=date(2025, 1, 5))  # Jan 5, 2025 is Sunday
        s, e = trading_day_window(clock, days=1)
        self.assertEqual(str(s.date()), '2025-01-03')
        self.assertEqual(str((e - pd.Timedelta(days=1)).date()), '2025-01-03')

    def test_fake_provider_slice(self):
        idx = pd.to_datetime(["2025-01-02", "2025-01-03"])
        df = pd.DataFrame({
            "Open": [1, 1], "High": [2, 2], "Low": [0.5, 0.5], "Close": [1.5, 1.6], "Adj Close": [1.5, 1.6], "Volume": [10, 20]
        }, index=idx)
        provider = FakeProvider(frames={"AAPL": df})
        clock = Clock(as_of=date(2025, 1, 3))
        s, e = trading_day_window(clock, days=1)
        out = provider.download("AAPL", s.to_pydatetime(), e.to_pydatetime())
        self.assertEqual(out.source, "fake")
        self.assertFalse(out.df.empty)
        self.assertEqual(len(out.df), 1)


if __name__ == '__main__':
    unittest.main()

