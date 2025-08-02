#!/usr/bin/env python3
"""
Gunicorn configuration for Sipeed NanoCluster Server Service
Reads configuration from config.yaml
"""

from src.server_config_manager import ConfigManager

config_manager = ConfigManager('config.yaml')
server_host, server_port = config_manager.get_server_config()

# Gunicorn configuration
bind = f"{server_host}:{server_port}"
workers = 1
worker_class = "sync"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = True
user = None  # Will be set by systemd
group = None  # Will be set by systemd
