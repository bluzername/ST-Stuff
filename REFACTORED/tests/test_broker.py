import unittest

from REFACTORED.microcap.brokers.base import NullBroker
from REFACTORED.microcap.brokers.ib_client_portal import ClientPortalGateway


class TestBroker(unittest.TestCase):
    def test_null_broker_cycle(self):
        b = NullBroker()
        self.assertTrue(b.authenticate())
        self.assertTrue(len(b.get_accounts()) >= 1)
        res = b.place_order({"ticker": "AAPL", "quantity": 1})
        self.assertIn("order_id", res)
        self.assertTrue(b.cancel_order(res["order_id"]))

    def test_cp_gateway_simulated_when_unavailable(self):
        g = ClientPortalGateway(config_path="nonexistent.yaml")
        self.assertTrue(g.authenticate())
        self.assertEqual(g.get_accounts()[0], "TEST")
        res = g.place_order({"ticker": "AAPL", "quantity": 1})
        self.assertEqual(res.get("status"), "SIMULATED")


if __name__ == '__main__':
    unittest.main()

