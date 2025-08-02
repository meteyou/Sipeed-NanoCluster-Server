#!/usr/bin/env python3
"""
Gunicorn configuration loader for Sipeed NanoCluster Client Service
Reads configuration from client_config.yaml
"""
from src.client_config import load_config

client_config = load_config(None, 'client_config.yaml')

# Set host and port from configuration or use defaults
client_host = client_config.get('host', '0.0.0.0')
client_port = client_config.get('port', 5001)

# Gunicorn configuration
bind = f"{client_host}:{client_port}"
workers = 1
worker_class = "sync"
timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = True
user = None  # Will be set by systemd
group = None  # Will be set by systemd
