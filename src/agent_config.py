import os
import yaml

DEFAULT_THERMAL_PATH = "/sys/class/thermal/thermal_zone0/temp"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5001

def load_config(logger, config_file='client_config.yaml'):
    """Load configuration from YAML file"""
    config_path = os.path.join(os.path.dirname(__file__), config_file)

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
    except Exception as e:
        logger.warning(f"Could not load config file {config_path}: {e}")

    # Return default config if file doesn't exist or can't be loaded
    return {
        'server': {
            'host': DEFAULT_HOST,
            'port': DEFAULT_PORT,
            'debug': False
        },
        'temperature': {
            'thermal_path': DEFAULT_THERMAL_PATH
        },
        'logging': {
            'level': 'INFO'
        }
    }