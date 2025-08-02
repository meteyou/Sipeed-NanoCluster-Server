import yaml
import os
from typing import Dict, List, Any


class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load the configuration from the YAML file"""
        if not os.path.exists(self.config_path):
            self.create_default_config()

        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file) or {}

    def create_default_config(self):
        """Create a default configuration file"""
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 5000
            },
            'nodes': [
                {
                    'name': 'example-node',
                    'slot': 1,
                    'ip': '192.168.0.100',
                    'port': 5000,
                    'enabled': True
                }
            ],
            'fan': {
                'gpio_pin': 13,
                'min_temp': 40,
                'max_temp': 70,
                'min_speed': 30,
                'max_speed': 100
            },
            'temperature_monitoring': {
                'interval_seconds': 10,
                'endpoint': '/api/temperature',
                'timeout': 5
            }
        }

        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as file:
            yaml.dump(default_config, file, default_flow_style=False)

    def get_nodes(self) -> List[Dict[str, Any]]:
        """Get all nodes from the configuration"""
        return self.config.get('nodes', [])

    def get_enabled_nodes(self) -> List[Dict[str, Any]]:
        """Get all enabled nodes from the configuration"""
        return [node for node in self.get_nodes() if node.get('enabled', False)]

    def get_fan_config(self) -> Dict[str, Any]:
        """Get the fan configuration"""
        return self.config.get('fan', {})

    def get_server_config(self) -> (str, int):
        """Get the server configuration"""
        server = self.config.get('server', {})
        host = server.get('host', '0.0.0.0')
        port = server.get('port', 5000)

        return host, port

    def add_node(self, name: str, slot: int, ip: str, port: int = 5000, enabled: bool = True):
        """Add a new node to the configuration"""
        nodes = self.config.get('nodes', [])
        nodes.append({
            'name': name,
            'slot': slot,
            'ip': ip,
            'port': port,
            'enabled': enabled
        })
        self.config['nodes'] = nodes
        self.save_config()

    def save_config(self):
        """Store the current configuration to the YAML file"""
        with open(self.config_path, 'w') as file:
            yaml.dump(self.config, file, default_flow_style=False)

    def get_temperature_monitoring_config(self) -> Dict[str, Any]:
        """Get the temperature monitoring configuration"""
        return self.config.get('temperature_monitoring', {})
