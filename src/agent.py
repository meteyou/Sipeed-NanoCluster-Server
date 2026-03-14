#!/usr/bin/env python3
"""
Sipeed NanoCluster Agent Service
A lightweight Flask service that provides system metrics via HTTP API.
This service is designed to run on each cluster node.
"""

from flask import Flask, jsonify
import os
import subprocess
import logging
import atexit
from waitress import serve

from agent_config import load_config, DEFAULT_THERMAL_PATH, DEFAULT_HOST, DEFAULT_PORT
from agent_temperature_reader import AgentTemperatureReader
from agent_system_reader import AgentSystemReader, PSUTIL_AVAILABLE

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config(logger, "../agent_config.yaml")

# Configure logging from config
log_level = config.get('logging', {}).get('level', 'INFO')
logging.getLogger().setLevel(getattr(logging, log_level.upper()))

app = Flask(__name__)

# Initialize temperature reader with config (backward compatibility)
thermal_path = config.get('temperature', {}).get('thermal_path', DEFAULT_THERMAL_PATH)
temp_reader = AgentTemperatureReader(logger, thermal_path)

# Initialize system reader (comprehensive metrics)
system_reader = None
if PSUTIL_AVAILABLE:
    system_reader = AgentSystemReader(logger, thermal_path)
    atexit.register(system_reader.stop)
    logger.info("System reader initialized (psutil available)")
else:
    logger.warning("psutil not installed – /api/system endpoint disabled")

# Device description from config
device_description = config.get('device', {}).get('description', '')


@app.route('/api/system', methods=['GET'])
def get_system():
    """
    API endpoint returning comprehensive system metrics.
    Includes CPU, memory, disk, network, temperature, and more.
    """
    if system_reader is None or not system_reader.available:
        return jsonify({
            'success': False,
            'error': 'psutil not available – install with: pip install psutil',
        }), 503

    data = system_reader.get_system_data(description=device_description)
    data['success'] = True
    return jsonify(data)


@app.route('/api/temperature', methods=['GET'])
def get_temperature():
    """
    API endpoint to get the current system temperature (backward compatible).
    Returns JSON with temperature in Celsius or error message.
    """
    temperature = temp_reader.read_temperature()

    if temperature is not None:
        return jsonify({
            'success': True,
            'temperature': temperature,
            'unit': 'celsius',
            'thermal_path': temp_reader.thermal_path
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to read temperature',
            'thermal_path': temp_reader.thermal_path
        }), 500


@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    """
    API endpoint to shut down this node.
    Executes 'sudo shutdown -h now' after a short delay so the response can be sent.
    """
    logger.warning("Shutdown requested via API!")

    try:
        subprocess.Popen(
            ["sudo", "shutdown", "-h", "+0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return jsonify({
            'success': True,
            'message': 'Shutdown initiated'
        })
    except Exception as e:
        logger.error(f"Failed to initiate shutdown: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to initiate shutdown: {e}'
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint to verify service is running.
    """
    return jsonify({
        'success': True,
        'status': 'healthy',
        'service': 'nanocluster-agent',
        'thermal_path': temp_reader.thermal_path,
        'thermal_available': os.path.exists(temp_reader.thermal_path),
        'psutil_available': PSUTIL_AVAILABLE,
    })


@app.route('/', methods=['GET'])
def index():
    """
    Simple index page with service information and links.
    """
    temperature = temp_reader.read_temperature()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sipeed NanoCluster Agent</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .card {{ background: white; border-radius: 8px; padding: 20px; margin: 16px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .success {{ border-left: 4px solid #10b981; }}
            .error {{ border-left: 4px solid #ef4444; }}
            .info {{ border-left: 4px solid #3b82f6; }}
            h1 {{ color: #1a1a2e; }}
            h3 {{ margin-top: 0; }}
            a {{ color: #3b82f6; }}
            code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 4px; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Sipeed NanoCluster Agent</h1>
            {f'<p><strong>{device_description}</strong></p>' if device_description else ''}
            <div class="card info">
                <h3>Service Information</h3>
                <p><strong>Thermal Path:</strong> <code>{temp_reader.thermal_path}</code></p>
                <p><strong>File Exists:</strong> {os.path.exists(temp_reader.thermal_path)}</p>
                <p><strong>psutil Available:</strong> {PSUTIL_AVAILABLE}</p>
            </div>
    """

    if temperature is not None:
        html += f"""
            <div class="card success">
                <h3>Current Temperature</h3>
                <p style="font-size: 24px; font-weight: bold;">{temperature:.1f}°C</p>
            </div>
        """
    else:
        html += """
            <div class="card error">
                <h3>Temperature Reading Failed</h3>
                <p>Unable to read temperature from thermal zone.</p>
            </div>
        """

    html += """
            <div class="card info">
                <h3>API Endpoints</h3>
                <ul>
                    <li><a href="/api/system">/api/system</a> – Full system metrics</li>
                    <li><a href="/api/temperature">/api/temperature</a> – Temperature only</li>
                    <li><a href="/api/health">/api/health</a> – Health check</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

    return html


if __name__ == '__main__':
    server_config = config.get('server', {})
    host = server_config.get('host', DEFAULT_HOST)
    port = server_config.get('port', DEFAULT_PORT)

    logger.info(f"Starting NanoCluster Agent on {host}:{port}")
    logger.info(f"Thermal zone path: {temp_reader.thermal_path}")
    if device_description:
        logger.info(f"Device description: {device_description}")

    try:
        serve(app, host=host, port=port)
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service failed to start: {e}")
