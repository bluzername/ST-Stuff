"""
Configuration Manager for IB Trading Module

Handles loading and validation of YAML configuration files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List
import logging


class ConfigManager:
    """Manages configuration loading and validation"""
    
    DEFAULT_CONFIG = {
        'connection': {
            'host': '127.0.0.1',
            'port': 7497,
            'client_id': 1,
            'account': '',
            'timeout': 10
        },
        'execution': {
            'mode': 'paper',
            'max_order_value': 10000,
            'require_confirmation': True,
            'order_timeout': 60
        },
        'monitoring': {
            'data_directories': ['../Start Your Own'],
            'poll_interval': 60
        },
        'logging': {
            'execution_csv': 'ib_execution_log.csv',
            'checkpoint_file': '.ib_checkpoint.json',
            'verbose': True
        },
        'safety': {
            'max_daily_trades': 50,
            'min_price': 0.01,
            'max_price': 1000,
            'max_quantity': 10000,
            'allowed_order_types': ['MKT', 'LMT']
        }
    }
    
    def __init__(self, config_path: str = "ib_config.yaml"):
        self.config_path = Path(config_path)
        self.config = self.DEFAULT_CONFIG.copy()
        self.logger = logging.getLogger(__name__)
        
        if self.config_path.exists():
            self.load_config()
        else:
            self.logger.warning(f"Config file {config_path} not found, using defaults")
    
    def load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                user_config = yaml.safe_load(f)
            
            if user_config:
                self._deep_update(self.config, user_config)
            
            self._validate_config()
            self.logger.info(f"Loaded config from {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            self.logger.info("Using default configuration")
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """Recursively update nested dictionary"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def _validate_config(self) -> None:
        """Validate configuration values"""
        
        # Validate connection settings
        conn = self.config['connection']
        if 'port' in conn and (not isinstance(conn['port'], int) or conn['port'] <= 0):
            raise ValueError("Connection port must be positive integer")
        
        if 'client_id' in conn and (not isinstance(conn['client_id'], int) or conn['client_id'] < 0):
            raise ValueError("Client ID must be non-negative integer")
        
        # Validate execution mode
        exec_config = self.config['execution']
        if 'mode' in exec_config and exec_config['mode'] not in ['paper', 'live']:
            raise ValueError("Execution mode must be 'paper' or 'live'")
        
        if 'max_order_value' in exec_config and exec_config['max_order_value'] <= 0:
            raise ValueError("Max order value must be positive")
        
        # Validate safety limits
        safety = self.config['safety']
        if 'min_price' in safety and safety['min_price'] <= 0:
            raise ValueError("Min price must be positive")
        
        if ('max_price' in safety and 'min_price' in safety and 
            safety['max_price'] <= safety['min_price']):
            raise ValueError("Max price must be greater than min price")
        
        if 'max_quantity' in safety and safety['max_quantity'] <= 0:
            raise ValueError("Max quantity must be positive")
        
        # Validate data directories exist
        for data_dir in self.config['monitoring']['data_directories']:
            dir_path = Path(data_dir)
            if not dir_path.exists():
                self.logger.warning(f"Data directory does not exist: {dir_path}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get config value using dot notation
        e.g., get('connection.host') returns config['connection']['host']
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_connection_params(self) -> Dict[str, Any]:
        """Get IB connection parameters"""
        return {
            'host': self.get('connection.host'),
            'port': self.get('connection.port'),
            'client_id': self.get('connection.client_id'),
            'timeout': self.get('connection.timeout')
        }
    
    def get_data_directories(self) -> List[str]:
        """Get list of data directories to monitor"""
        return self.get('monitoring.data_directories', [])
    
    def is_paper_trading(self) -> bool:
        """Check if paper trading mode is enabled"""
        return self.get('execution.mode') == 'paper'
    
    def require_confirmation(self) -> bool:
        """Check if trade confirmation is required"""
        return self.get('execution.require_confirmation', True)
    
    def validate_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Validate trade against safety limits"""
        
        # Check price limits
        price = trade_data.get('price', 0)
        if price < self.get('safety.min_price', 0.01):
            self.logger.warning(f"Price {price} below minimum {self.get('safety.min_price')}")
            return False
        
        if price > self.get('safety.max_price', 1000):
            self.logger.warning(f"Price {price} above maximum {self.get('safety.max_price')}")
            return False
        
        # Check quantity limits
        quantity = trade_data.get('quantity', 0)
        if quantity > self.get('safety.max_quantity', 10000):
            self.logger.warning(f"Quantity {quantity} above maximum {self.get('safety.max_quantity')}")
            return False
        
        # Check order value
        order_value = price * quantity
        max_value = self.get('execution.max_order_value', 10000)
        if order_value > max_value:
            self.logger.warning(f"Order value ${order_value:.2f} above maximum ${max_value:.2f}")
            return False
        
        # Check order type
        order_type = trade_data.get('order_type', '')
        allowed_types = self.get('safety.allowed_order_types', ['MKT', 'LMT'])
        if order_type not in allowed_types:
            self.logger.warning(f"Order type {order_type} not in allowed types: {allowed_types}")
            return False
        
        return True
    
    def save_config(self, path: str = None) -> None:
        """Save current configuration to file"""
        save_path = Path(path) if path else self.config_path
        
        try:
            with open(save_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            self.logger.info(f"Saved config to {save_path}")
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
    
    def print_config(self) -> None:
        """Print current configuration"""
        print("Current Configuration:")
        print(yaml.dump(self.config, default_flow_style=False, indent=2))