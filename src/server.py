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
config_manager = ConfigManager()

# Initialize temperature monitor
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
