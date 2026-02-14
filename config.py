"""
Configuration settings for SynergyPlus
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Network settings
DEFAULT_PORT = 9999
DEFAULT_HOST = '0.0.0.0'
BUFFER_SIZE = 4096
CONNECTION_TIMEOUT = 30

# Protocol settings
PROTOCOL_VERSION = '1.0'

# Logging settings
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Configuration directory
CONFIG_DIR = Path.home() / '.synergyplus'
MASTER_CONFIG_FILE = CONFIG_DIR / 'master_config.json'
SERVER_CONFIG_FILE = CONFIG_DIR / 'server_config.json'


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_file: Path, default_config: Dict[str, Any]):
        self.config_file = config_file
        self.default_config = default_config
        self.config = {}
        self._ensure_config_dir()
        self.load()
    
    def _ensure_config_dir(self):
        """Ensure configuration directory exists"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                # Merge with defaults for missing keys
                self.config = self._merge_configs(self.default_config, self.config)
            except Exception as e:
                print(f"Error loading config: {e}, using defaults")
                self.config = self.default_config.copy()
        else:
            self.config = self.default_config.copy()
        return self.config
    
    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str, default=None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value by key (supports dot notation)"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def _merge_configs(self, default: Dict, user: Dict) -> Dict:
        """Merge user config with default config"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result


# Default configurations
DEFAULT_MASTER_CONFIG = {
    "version": "1.0",
    "network": {
        "default_port": DEFAULT_PORT,
        "connection_timeout": CONNECTION_TIMEOUT
    },
    "behavior": {
        "auto_connect": False,
        "last_active_server": "",
        "control_hotkey": "ctrl+shift+s"
    },
    "servers": []
}

DEFAULT_SERVER_CONFIG = {
    "version": "1.0",
    "network": {
        "port": DEFAULT_PORT
    },
    "behavior": {
        "auto_start": False
    },
    "security": {
        "enable_whitelist": False,
        "whitelist": []
    }
}


def get_master_config() -> ConfigManager:
    """Get master configuration manager"""
    return ConfigManager(MASTER_CONFIG_FILE, DEFAULT_MASTER_CONFIG)


def get_server_config() -> ConfigManager:
    """Get server configuration manager"""
    return ConfigManager(SERVER_CONFIG_FILE, DEFAULT_SERVER_CONFIG)

