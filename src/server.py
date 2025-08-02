from flask import Flask, render_template, jsonify
from src.server_config_manager import ConfigManager
from src.server_temperature_monitor import TemperatureMonitor
import logging
import atexit
import os
from typing import Optional

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
config_manager = ConfigManager()
temperature_monitor: Optional[TemperatureMonitor] = None
_monitor_initialized = False


def init_temperature_monitor() -> None:
    """Initialize temperature monitor - called when worker starts"""
    global temperature_monitor, _monitor_initialized
    if temperature_monitor is None and not _monitor_initialized:
        logger.info("Initializing temperature monitor in worker process")
        temperature_monitor = TemperatureMonitor(config_manager)
        temperature_monitor.start_monitoring()
        _monitor_initialized = True
        # Register shutdown handler to stop monitoring on exit
        atexit.register(temperature_monitor.stop_monitoring)


def get_temperature_monitor() -> TemperatureMonitor:
    """Get temperature monitor instance, initialize if needed"""
    global temperature_monitor
    if temperature_monitor is None:
        init_temperature_monitor()

    # Type narrowing: Nach init_temperature_monitor() ist temperature_monitor garantiert nicht None
    if temperature_monitor is None:
        raise RuntimeError("Failed to initialize temperature monitor")

    return temperature_monitor


# Initialize temperature monitor when running directly (not with Gunicorn preload)
if not os.environ.get('SERVER_SOFTWARE', '').startswith('gunicorn'):
    init_temperature_monitor()


@app.route('/')
def index():
    """Overview page with all nodes and fan configuration"""
    return render_template('index.html')


@app.route('/api/nodes')
def api_nodes():
    """API endpoint to get all nodes"""
    nodes = config_manager.get_nodes()
    return jsonify(nodes)


@app.route('/api/nodes/temperatures')
def api_nodes_temperatures():
    """API endpoint to get all nodes"""
    monitor = get_temperature_monitor()
    latest_temps = monitor.get_latest_temperatures()
    return jsonify({
        'success': True,
        'temperatures': latest_temps
    })


@app.route('/api/fan/config')
def api_fan_config():
    """API endpoint to get fan configuration"""
    fan_config = config_manager.get_fan_config()
    return jsonify(fan_config)


@app.route('/api/fan/status')
def api_fan_status():
    """API endpoint to get fan status"""
    monitor = get_temperature_monitor()
    fan_speed = monitor.get_fan_speed()
    return jsonify({
        'success': True,
        'fan_speed': fan_speed
    })


if __name__ == '__main__':
    host, port = config_manager.get_server_config()
    app.run(host=host, port=port, debug=True)
