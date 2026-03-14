import os

# Resolve paths relative to the project root before changing the working directory
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_config_path = os.path.join(_project_root, 'config.yaml')

# Change to a writable directory before importing lgpio (via TemperatureMonitor),
# as lgpio creates notification pipe files in the current working directory.
# When running as a systemd service, RuntimeDirectory provides /run/<service-name>/
runtime_dir = os.environ.get('RUNTIME_DIRECTORY', '/tmp')
os.chdir(runtime_dir)

from flask import Flask, render_template, jsonify, request
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

    fan_mode = temperature_monitor.get_fan_mode()

    return jsonify({
        'success': True,
        'nodes': nodes,
        'fan': {
            'config': fan_config,
            'speed': fan_speed,
            'mode': fan_mode,
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


@app.route('/api/nodes/status')
def api_nodes_status():
    """API endpoint to get online/offline status of all nodes"""
    statuses = temperature_monitor.get_node_statuses()
    return jsonify({
        'success': True,
        'statuses': statuses
    })


@app.route('/api/nodes/<node_name>/shutdown', methods=['POST'])
def api_node_shutdown(node_name):
    """API endpoint to shut down a specific node via its agent"""
    nodes = config_manager.get_nodes()
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return jsonify({'success': False, 'error': f'Node {node_name} not found'}), 404

    success = temperature_monitor.shutdown_node(node)
    return jsonify({
        'success': success,
        'message': f'Shutdown {"initiated" if success else "failed"} for {node_name}'
    })


@app.route('/api/cluster/shutdown', methods=['POST'])
def api_cluster_shutdown():
    """Shut down all non-master nodes (all except slot 1)"""
    nodes = config_manager.get_nodes()
    master_slot = 1
    results = {}

    for node in nodes:
        if node['slot'] == master_slot:
            continue
        if not node.get('enabled', False):
            continue
        success = temperature_monitor.shutdown_node(node)
        results[node['name']] = success

    return jsonify({
        'success': True,
        'results': results
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
    fan_mode = temperature_monitor.get_fan_mode()
    return jsonify({
        'success': True,
        'fan_speed': fan_speed,
        'fan_mode': fan_mode,
    })


@app.route('/api/fan/override', methods=['POST'])
def api_fan_override():
    """Set manual fan speed override (0–100)"""
    data = request.get_json(silent=True) or {}
    speed = data.get('speed')
    if speed is None:
        return jsonify({'success': False, 'error': 'Missing "speed" parameter'}), 400
    try:
        speed = int(speed)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': '"speed" must be an integer (0–100)'}), 400
    if not (0 <= speed <= 100):
        return jsonify({'success': False, 'error': '"speed" must be between 0 and 100'}), 400

    temperature_monitor.set_manual_speed(speed)
    return jsonify({'success': True, 'mode': 'manual', 'speed': speed})


@app.route('/api/fan/auto', methods=['POST'])
def api_fan_auto():
    """Switch fan back to automatic mode"""
    temperature_monitor.set_auto_mode()
    return jsonify({'success': True, 'mode': 'auto', 'speed': temperature_monitor.get_fan_speed()})


@app.route('/api/fan/config', methods=['POST'])
def api_fan_config_update():
    """Update fan configuration and save to config.yaml"""
    data = request.get_json(silent=True) or {}

    # Validate and convert numeric fields
    updates = {}
    int_fields = {
        'min_temp': (0, 120),
        'max_temp': (0, 120),
        'min_speed': (0, 100),
        'max_speed': (0, 100),
        'pwm_frequency': (1, 100000),
    }

    for field, (lo, hi) in int_fields.items():
        if field in data:
            try:
                val = int(data[field])
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': f'"{field}" must be an integer'}), 400
            if not (lo <= val <= hi):
                return jsonify({'success': False, 'error': f'"{field}" must be between {lo} and {hi}'}), 400
            updates[field] = val

    if 'pwm_reverse' in data:
        updates['pwm_reverse'] = bool(data['pwm_reverse'])

    if not updates:
        return jsonify({'success': False, 'error': 'No valid fields to update'}), 400

    config_manager.update_fan_config(updates)
    temperature_monitor.apply_fan_config()

    return jsonify({'success': True, 'config': config_manager.get_fan_config()})


if __name__ == '__main__':
    host, port = config_manager.get_server_config()
    serve(app, host=host, port=port)
