import os

# Resolve paths relative to the project root before changing the working directory
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_config_path = os.path.join(_project_root, 'config.yaml')

# Change to a writable directory before importing lgpio (via TemperatureMonitor),
# as lgpio creates notification pipe files in the current working directory.
# When running as a systemd service, RuntimeDirectory provides /run/<service-name>/
runtime_dir = os.environ.get('RUNTIME_DIRECTORY', '/tmp')
os.chdir(runtime_dir)

from flask import Flask, render_template, jsonify
from server_config_manager import ConfigManager
from server_temperature_monitor import TemperatureMonitor
import logging
import atexit
from waitress import serve

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
config_manager = ConfigManager(config_path=_config_path)

# Initialize temperature monitor
temperature_monitor = TemperatureMonitor(config_manager)
temperature_monitor.start_monitoring()

# Register shutdown handler to stop monitoring on exit
atexit.register(temperature_monitor.stop_monitoring)


@app.route('/')
def index():
    """Overview page with all nodes and fan configuration"""
    return render_template('index.html')


@app.route('/api/dashboard')
def api_dashboard():
    """
    Single comprehensive endpoint that returns all dashboard data:
    node config + system metrics + fan status.
    """
    nodes_config = config_manager.get_nodes()
    system_data = temperature_monitor.get_system_data()
    latest_temps = temperature_monitor.get_latest_temperatures()
    fan_config = config_manager.get_fan_config()
    fan_speed = temperature_monitor.get_fan_speed()

    nodes = []
    for node in sorted(nodes_config, key=lambda n: n.get('slot', 0)):
        name = node['name']
        sys_info = system_data.get(name)
        temp_info = latest_temps.get(name)

        entry = {
            'name': name,
            'slot': node.get('slot', 0),
            'ip': node.get('ip', ''),
            'port': node.get('port', 5001),
            'enabled': node.get('enabled', False),
            'description': node.get('description', ''),
            'online': sys_info is not None or temp_info is not None,
            'system': sys_info,  # may be None if agent doesn't support /api/system
        }

        # If we have system data, the temperature and timestamp are included.
        # Otherwise fall back to the legacy temperature-only data.
        if sys_info is None and temp_info:
            entry['temperature'] = temp_info.get('temperature')
            entry['last_update'] = temp_info.get('timestamp')
        elif sys_info:
            entry['temperature'] = sys_info.get('temperature')
            entry['last_update'] = sys_info.get('timestamp')
        else:
            entry['temperature'] = None
            entry['last_update'] = None

        nodes.append(entry)

    return jsonify({
        'success': True,
        'nodes': nodes,
        'fan': {
            'config': fan_config,
            'speed': fan_speed,
        },
    })


# ── Legacy API endpoints (kept for backward compatibility) ─────────────


@app.route('/api/nodes')
def api_nodes():
    """API endpoint to get all nodes"""
    nodes = config_manager.get_nodes()
    return jsonify(nodes)


@app.route('/api/nodes/temperatures')
def api_nodes_temperatures():
    """API endpoint to get all node temperatures"""
    latest_temps = temperature_monitor.get_latest_temperatures()
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
    fan_speed = temperature_monitor.get_fan_speed()
    return jsonify({
        'success': True,
        'fan_speed': fan_speed
    })


if __name__ == '__main__':
    host, port = config_manager.get_server_config()
    serve(app, host=host, port=port)
