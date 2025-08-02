from flask import Flask, render_template, jsonify
from server_config_manager import ConfigManager
from server_temperature_monitor import TemperatureMonitor
import logging
import atexit
import requests

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
config_manager = ConfigManager()
temperature_monitor = TemperatureMonitor(config_manager)
temperature_monitor.start_monitoring()

# Register shutdown handler to stop monitoring on exit
atexit.register(temperature_monitor.stop_monitoring)


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


@app.route('/api/nodes/<node_name>/temperature')
def api_node_temperature(node_name):
    """API endpoint to get temperature of a specific node by querying it directly"""
    # Find the node in configuration
    nodes = config_manager.get_nodes()
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return jsonify({
            'success': False,
            'error': f'Node {node_name} not found'
        }), 404

    if not node.get('enabled', False):
        return jsonify({
            'success': False,
            'error': f'Node {node_name} is disabled'
        }), 400

    # Try to get temperature from monitoring data first
    latest_temps = temperature_monitor.get_latest_temperatures()
    if node_name in latest_temps:
        temp_data = latest_temps[node_name]
        return jsonify({
            'success': True,
            'temperature': temp_data['temperature'],
            'timestamp': temp_data['timestamp'],
            'source': 'monitoring_cache'
        })

    # If not in cache, query the node directly
    temp_config = config_manager.get_temperature_monitoring_config()
    endpoint = temp_config.get('endpoint', '/api/temperature')
    timeout = temp_config.get('timeout', 5)

    try:
        url = f"http://{node['ip']}:{node['port']}{endpoint}"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        data = response.json()
        if data.get('success') and 'temperature' in data:
            return jsonify({
                'success': True,
                'temperature': data['temperature'],
                'source': 'direct_query'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid response from node'
            }), 500

    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Timeout connecting to node'
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Could not connect to node'
        }), 503
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error querying node: {str(e)}'
        }), 500


if __name__ == '__main__':
    host, port = config_manager.get_server_config()
    app.run(host=host, port=port, debug=True)
