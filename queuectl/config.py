import json
import os
from pathlib import Path
from typing import Dict, Any

# --- THIS IS THE KEY CHANGE ---
# Store data *inside* the project directory, not in the (synced) home dir.
# This finds the root of your project: ~/Programs/queuectl-py/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / ".queuectl_data"
# --- END OF CHANGE ---

APP_DIR.mkdir(exist_ok=True)

# Define file paths
DB_PATH = APP_DIR / "queue.db"
CONFIG_PATH = APP_DIR / "config.json"
PID_FILE = APP_DIR / "workers.pid"

# Default configuration
DEFAULT_CONFIG = {
    "max_retries": 3,
    "backoff_base": 2,  # delay = base ^ attempts
}

def load_config() -> Dict[str, Any]:
    """Loads configuration from file, creating it if non-existent."""
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    with open(CONFIG_PATH, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # If config is corrupted, reset to default
            save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG

def save_config(config: Dict[str, Any]):
    """Saves the configuration dictionary to the config file."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def get_config_value(key: str) -> Any:
    """Utility to get a single config value."""
    config = load_config()
    return config.get(key, DEFAULT_CONFIG.get(key))