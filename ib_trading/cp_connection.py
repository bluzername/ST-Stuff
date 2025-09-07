#!/usr/bin/env python3
"""
Client Portal Connection Manager

Simple, modular REST API wrapper for Interactive Brokers Client Portal Gateway.
No overengineering, no magic numbers, just clean HTTP requests.

Author: Someone who believes REST should be RESTful
"""

import requests
import yaml
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from urllib3.exceptions import InsecureRequestWarning
from dataclasses import dataclass

# Disable SSL warnings for self-signed certs
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


@dataclass
class OrderResult:
    """Order placement result"""
    order_id: str
    status: str
    message: str
    raw_response: Dict[str, Any]


class ClientPortalError(Exception):
    """Custom exception for Client Portal API errors"""
    pass


class ClientPortalConnection:
    """
    REST API wrapper for IB Client Portal Gateway
    
    Handles authentication, order placement, contract resolution,
    and account management through HTTP requests.
    """
    
    def __init__(self, config_path: str = "cp_config.yaml"):
        """Initialize connection with configuration"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # Extract configuration sections
        self.cp_config = self.config['client_portal']
        self.trading_config = self.config['trading']
        self.safety_config = self.trading_config['safety']
        
        # Build base URL
        self.base_url = self.cp_config['base_url']
        
        # Setup HTTP session
        self.session = self._create_session()
        
        # Connection state
        self.authenticated = False
        self.account_id = None
        self.available_accounts = []
        
        # Setup logging
        self.logger = self._setup_logging()
        
        self.logger.info(f"Client Portal connection initialized")
        self.logger.info(f"Base URL: {self.base_url}")
        self.logger.info(f"Trading mode: {self.trading_config['mode']}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with proper settings"""
        session = requests.Session()
        
        # SSL configuration
        session.verify = self.cp_config['ssl']['verify']
        if self.cp_config['ssl']['cert_file']:
            session.cert = (
                self.cp_config['ssl']['cert_file'],
                self.cp_config['ssl']['key_file']
            )
        
        # Headers
        session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TradingPipeline-ClientPortal/1.0',
            'Accept': 'application/json'
        })
        
        return session
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for API calls"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config['logging']['level']))
        
        if not logger.handlers:
            handler = logging.FileHandler(self.config['logging']['files']['api_log'])
            formatter = logging.Formatter(self.config['logging']['format'])
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic and error handling
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional requests parameters
            
        Returns:
            JSON response as dictionary
            
        Raises:
            ClientPortalError: On API errors or connection failures
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Apply timeouts from config
        kwargs.setdefault('timeout', (
            self.cp_config['timeouts']['connect'],
            self.cp_config['timeouts']['read']
        ))
        
        retry_config = self.cp_config['retry']
        
        for attempt in range(retry_config['max_attempts']):
            try:
                self.logger.debug(f"API Request: {method} {url}")
                
                response = self.session.request(method, url, **kwargs)
                
                self.logger.debug(f"API Response: {response.status_code}")
                
                # Handle different response codes
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    self.authenticated = False
                    raise ClientPortalError("Authentication required")
                elif response.status_code == 429:
                    self.logger.warning("Rate limit exceeded")
                    time.sleep(retry_config['retry_delay'] * 2)
                    continue
                else:
                    response.raise_for_status()
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"Request timeout (attempt {attempt + 1})")
            except requests.exceptions.ConnectionError:
                self.logger.warning(f"Connection error (attempt {attempt + 1})")
            except requests.exceptions.HTTPError as e:
                self.logger.error(f"HTTP error: {e}")
                if response.status_code < 500:  # Client error, don't retry
                    raise ClientPortalError(f"HTTP {response.status_code}: {response.text}")
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                raise ClientPortalError(f"Request failed: {e}")
            
            # Wait before retry
            if attempt < retry_config['max_attempts'] - 1:
                delay = retry_config['retry_delay'] * (retry_config['backoff_factor'] ** attempt)
                self.logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
        
        raise ClientPortalError(f"Request failed after {retry_config['max_attempts']} attempts")
    
    def check_connection(self) -> bool:
        """Test if Client Portal Gateway is accessible"""
        try:
            # Try the tickle endpoint first
            response = self._request('GET', 'tickle')
            if response.get('tickle') or str(response.get('tickle')).lower() == 'true':
                return True
                
            # Fallback to auth status
            response = self._request('GET', 'iserver/auth/status')
            return 'authenticated' in response
            
        except Exception as e:
            self.logger.error(f"Connection check failed: {e}")
            return False
    
    def authenticate(self) -> bool:
        """
        Check authentication status and authenticate if needed
        
        Returns:
            True if authenticated, False otherwise
        """
        try:
            # Check current auth status
            status = self._request('GET', 'iserver/auth/status')
            
            self.authenticated = status.get('authenticated', False)
            
            if self.authenticated:
                self.logger.info("Already authenticated with Client Portal")
                return True
            
            # If not authenticated, we can't do much automatically
            # User needs to authenticate through the Client Portal web interface
            self.logger.error("Not authenticated - please authenticate through Client Portal web interface")
            return False
            
        except Exception as e:
            self.logger.error(f"Authentication check failed: {e}")
            return False
    
    def get_accounts(self) -> List[str]:
        """
        Get list of available trading accounts
        
        Returns:
            List of account IDs
        """
        try:
            accounts = self._request('GET', 'portfolio/accounts')
            self.available_accounts = [acc.get('accountId', acc.get('id', '')) for acc in accounts]
            
            # Set default account if not specified
            if not self.account_id and self.available_accounts:
                self.account_id = self.available_accounts[0]
                self.logger.info(f"Using default account: {self.account_id}")
            
            return self.available_accounts
            
        except Exception as e:
            self.logger.error(f"Failed to get accounts: {e}")
            return []
    
    def get_contract_id(self, ticker: str) -> Optional[int]:
        """
        Get contract ID for a stock ticker
        
        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            
        Returns:
            Contract ID (conid) or None if not found
        """
        try:
            # Search for contract
            response = self._request('GET', 'iserver/secdef/search', params={
                'symbol': ticker.upper(),
                'secType': 'STK'
            })
            
            if not response:
                self.logger.error(f"No contracts found for ticker: {ticker}")
                return None
            
            # Get the first match (usually the primary exchange)
            contract = response[0]
            conid = contract.get('conid')
            
            if conid:
                self.logger.info(f"Resolved {ticker} to contract ID: {conid}")
                return int(conid)
            else:
                self.logger.error(f"No contract ID found for ticker: {ticker}")
                return None
                
        except Exception as e:
            self.logger.error(f"Contract resolution failed for {ticker}: {e}")
            return None
    
    def validate_order(self, order_data: Dict[str, Any]) -> bool:
        """
        Validate order against safety limits
        
        Args:
            order_data: Order dictionary with ticker, action, quantity, price
            
        Returns:
            True if order passes validation
        """
        ticker = order_data.get('ticker', '').upper()
        action = order_data.get('action', '').upper()
        quantity = float(order_data.get('quantity', 0))
        price = float(order_data.get('price', 0))
        order_type = order_data.get('order_type', 'LMT').upper()
        
        # Check forbidden tickers
        if ticker in self.safety_config['forbidden_tickers']:
            self.logger.error(f"Order rejected: {ticker} is forbidden")
            return False
        
        # Check order type
        if order_type not in self.safety_config['allowed_order_types']:
            self.logger.error(f"Order rejected: {order_type} not allowed")
            return False
        
        # Check quantity
        if quantity <= 0 or quantity > self.safety_config['max_quantity']:
            self.logger.error(f"Order rejected: quantity {quantity} outside limits")
            return False
        
        # Check price
        if price < self.safety_config['min_price'] or price > self.safety_config['max_price']:
            self.logger.error(f"Order rejected: price {price} outside limits")
            return False
        
        # Check order value
        order_value = quantity * price
        if order_value > self.safety_config['max_order_value']:
            self.logger.error(f"Order rejected: value ${order_value:.2f} exceeds limit")
            return False
        
        self.logger.info(f"Order validation passed: {action} {quantity} {ticker} @ ${price:.2f}")
        return True
    
    def place_order(self, order_data: Dict[str, Any]) -> OrderResult:
        """
        Place an order through Client Portal API
        
        Args:
            order_data: Dictionary containing order details
            
        Returns:
            OrderResult with order ID and status
        """
        if not self.authenticated:
            raise ClientPortalError("Not authenticated - call authenticate() first")
        
        if not self.account_id:
            self.get_accounts()
            if not self.account_id:
                raise ClientPortalError("No account ID available")
        
        # Validate order
        if not self.validate_order(order_data):
            raise ClientPortalError("Order validation failed")
        
        # Get contract ID
        conid = self.get_contract_id(order_data['ticker'])
        if not conid:
            raise ClientPortalError(f"Could not resolve contract for {order_data['ticker']}")
        
        # Build Client Portal order format
        cp_order = {
            "acctId": self.account_id,
            "conid": conid,
            "secType": "STK",
            "orderType": order_data.get('order_type', 'LMT').upper(),
            "side": order_data['action'].upper(),
            "quantity": float(order_data['quantity']),
            "tif": self.trading_config['defaults']['time_in_force'],
            "outsideRTH": self.trading_config['defaults']['outside_rth']
        }
        
        # Add price for limit orders
        if cp_order['orderType'] in ['LMT', 'STP_LMT']:
            cp_order['price'] = float(order_data['price'])
        
        # Add stop price for stop orders
        if cp_order['orderType'] in ['STP', 'STP_LMT']:
            cp_order['auxPrice'] = float(order_data.get('stop_price', order_data['price']))
        
        try:
            self.logger.info(f"Placing order: {cp_order}")
            
            response = self._request('POST', f'iserver/account/{self.account_id}/orders', 
                                   json={"orders": [cp_order]})
            
            # Extract order result
            if isinstance(response, list) and len(response) > 0:
                order_response = response[0]
                
                return OrderResult(
                    order_id=str(order_response.get('order_id', order_response.get('orderId', 'unknown'))),
                    status=order_response.get('order_status', 'unknown'),
                    message=order_response.get('text', ''),
                    raw_response=order_response
                )
            else:
                raise ClientPortalError(f"Unexpected order response: {response}")
                
        except Exception as e:
            self.logger.error(f"Order placement failed: {e}")
            raise ClientPortalError(f"Order placement failed: {e}")
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status by order ID"""
        try:
            orders = self._request('GET', f'iserver/account/{self.account_id}/orders')
            
            for order in orders.get('orders', []):
                if str(order.get('orderId', order.get('order_id', ''))) == str(order_id):
                    return order
            
            self.logger.warning(f"Order {order_id} not found")
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to get order status: {e}")
            return {}
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by order ID"""
        try:
            response = self._request('DELETE', f'iserver/account/{self.account_id}/order/{order_id}')
            
            success = response.get('msg', '').lower() in ['order cancelled', 'cancelled']
            
            if success:
                self.logger.info(f"Order {order_id} cancelled successfully")
            else:
                self.logger.warning(f"Order {order_id} cancellation uncertain: {response}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions"""
        try:
            response = self._request('GET', f'portfolio/{self.account_id}/positions')
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return []
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary information"""
        try:
            response = self._request('GET', f'portfolio/{self.account_id}/summary')
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to get account summary: {e}")
            return {}
    
    def disconnect(self):
        """Clean disconnect"""
        self.session.close()
        self.logger.info("Client Portal connection closed")


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Client Portal Connection")
    parser.add_argument('--config', default='cp_config.yaml', help='Config file path')
    parser.add_argument('--test-order', action='store_true', help='Place test order')
    args = parser.parse_args()
    
    # Setup logging to console
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    cp = ClientPortalConnection(args.config)
    
    print("=== Client Portal Connection Test ===")
    
    # Test connection
    if cp.check_connection():
        print("✓ Client Portal is accessible")
    else:
        print("✗ Client Portal is not accessible")
        exit(1)
    
    # Test authentication
    if cp.authenticate():
        print("✓ Authentication successful")
    else:
        print("✗ Authentication failed")
        exit(1)
    
    # Get accounts
    accounts = cp.get_accounts()
    print(f"✓ Available accounts: {accounts}")
    
    # Test contract resolution
    conid = cp.get_contract_id('AAPL')
    if conid:
        print(f"✓ AAPL contract ID: {conid}")
    else:
        print("✗ Failed to resolve AAPL contract")
    
    # Test order placement if requested
    if args.test_order:
        test_order = {
            'ticker': 'AAPL',
            'action': 'BUY',
            'quantity': 1,
            'price': 100.00,  # Unlikely to fill
            'order_type': 'LMT'
        }
        
        try:
            result = cp.place_order(test_order)
            print(f"✓ Test order placed: {result.order_id}")
            
            # Cancel immediately
            if cp.cancel_order(result.order_id):
                print(f"✓ Test order cancelled: {result.order_id}")
            else:
                print(f"✗ Failed to cancel test order: {result.order_id}")
                
        except Exception as e:
            print(f"✗ Test order failed: {e}")
    
    cp.disconnect()
    print("=== Test completed ===")