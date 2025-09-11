from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List

try:
    # Best-effort import; not required for unit tests here
    from ib_trading.cp_connection import ClientPortalConnection  # type: ignore
    _HAS_CP = True
except Exception:
    _HAS_CP = False


@dataclass
class ClientPortalGateway:
    config_path: str = "ib_trading/cp_config.yaml"

    def __post_init__(self):
        if not _HAS_CP:
            self._cp = None
            return
        try:
            self._cp = ClientPortalConnection(self.config_path)
        except Exception:
            # Fall back to simulated gateway if config or runtime is invalid
            self._cp = None

    def authenticate(self) -> bool:
        return self._cp.authenticate() if self._cp else True

    def get_accounts(self) -> List[str]:
        return self._cp.get_accounts() if self._cp else ["TEST"]

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        if not self._cp:
            return {"order_id": "0", "status": "SIMULATED"}
        # Map schema if needed; here we pass through
        res = self._cp.place_order(order)
        return {"order_id": res.get("order_id", ""), "status": res.get("status", "")}

    def cancel_order(self, order_id: str) -> bool:
        return self._cp.cancel_order(order_id) if self._cp else True

    def get_positions(self) -> List[Dict[str, Any]]:
        return self._cp.get_positions() if self._cp else []

    def get_account_summary(self) -> Dict[str, Any]:
        return self._cp.get_account_summary() if self._cp else {"cash": 0}
