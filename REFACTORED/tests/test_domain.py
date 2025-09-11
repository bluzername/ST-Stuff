import unittest
from datetime import date

from REFACTORED.microcap.domain.models import Position


class TestDomainPosition(unittest.TestCase):
    def test_add_and_remove_shares(self):
        p = Position(ticker="AAPL", shares=10, buy_price=100.0, cost_basis=1000.0)
        p.add_shares(10, 110.0)
        self.assertEqual(p.shares, 20)
        self.assertAlmostEqual(p.buy_price, 105.0)
        self.assertAlmostEqual(p.cost_basis, 2100.0)

        realized = p.remove_shares(5, 120.0)
        self.assertEqual(p.shares, 15)
        self.assertAlmostEqual(realized, 5 * (120.0 - 105.0))
        self.assertAlmostEqual(p.cost_basis, 15 * 105.0)


if __name__ == '__main__':
    unittest.main()

