from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Dict, Any, List, Optional


class BrokerGateway(Protocol):
    def authenticate(self) -> bool: ...
    def get_accounts(self) -> List[str]: ...
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]: ...
    def cancel_order(self, order_id: str) -> bool: ...
    def get_positions(self) -> List[Dict[str, Any]]: ...
    def get_account_summary(self) -> Dict[str, Any]: ...


@dataclass
class NullBroker:
    """No-op broker for tests."""
    def authenticate(self) -> bool: return True
    def get_accounts(self) -> List[str]: return ["TEST"]
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]: return {"order_id": "0", "status": "OK"}
    def cancel_order(self, order_id: str) -> bool: return True
    def get_positions(self) -> List[Dict[str, Any]]: return []
    def get_account_summary(self) -> Dict[str, Any]: return {"cash": 0}

