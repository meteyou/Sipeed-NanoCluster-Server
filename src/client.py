#!/usr/bin/env python3
"""
Sipeed NanoCluster Client Service
A lightweight Flask service that provides temperature data via HTTP API.
This service is designed to run on each cluster node.
"""

from flask import Flask, jsonify
import os
import logging

from src.client_config import load_config, DEFAULT_THERMAL_PATH, DEFAULT_HOST, DEFAULT_PORT
from src.client_temperature_reader import ClientTemperatureReader

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config("../client_config.yaml")

# Configure logging from config
log_level = config.get('logging', {}).get('level', 'INFO')
logging.getLogger().setLevel(getattr(logging, log_level.upper()))

app = Flask(__name__)

# Initialize temperature reader with config
thermal_path = config.get('temperature', {}).get('thermal_path', DEFAULT_THERMAL_PATH)
temp_reader = ClientTemperatureReader(logger, thermal_path)


@app.route('/api/temperature', methods=['GET'])
def get_temperature():
    """
    API endpoint to get the current system temperature.
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


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint to verify service is running.
    """
    return jsonify({
        'success': True,
        'status': 'healthy',
        'service': 'temperature-client',
        'thermal_path': temp_reader.thermal_path,
        'thermal_available': os.path.exists(temp_reader.thermal_path)
    })


@app.route('/', methods=['GET'])
def index():
    """
    Simple index page with service information.
    """
    temperature = temp_reader.read_temperature()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sipeed NanoCluster Client Service</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .status {{ padding: 20px; border-radius: 5px; margin: 20px 0; }}
            .success {{ background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; }}
            .error {{ background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }}
            .info {{ background-color: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Sipeed NanoCluster Client Service</h1>
            <div class="info">
                <h3>Service Information</h3>
                <p><strong>Thermal Path:</strong> {temp_reader.thermal_path}</p>
                <p><strong>File Exists:</strong> {os.path.exists(temp_reader.thermal_path)}</p>
            </div>
    """

    if temperature is not None:
        html += f"""
            <div class="status success">
                <h3>Current Temperature</h3>
                <p><strong>{temperature:.2f}°C</strong></p>
            </div>
        """
    else:
        html += """
            <div class="status error">
                <h3>Temperature Reading Failed</h3>
                <p>Unable to read temperature from thermal zone.</p>
            </div>
        """

    html += """
            <div class="info">
                <h3>API Endpoints</h3>
                <ul>
                    <li><a href="/api/temperature">/api/temperature</a> - Get current temperature</li>
                    <li><a href="/api/health">/api/health</a> - Health check</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

    return html


if __name__ == '__main__':
    # When run directly (not via Gunicorn), use config for defaults
    server_config = config.get('server', {})
    host = server_config.get('host', DEFAULT_HOST)
    port = server_config.get('port', DEFAULT_PORT)
    debug = server_config.get('debug', False)

    logger.info(f"Starting Temperature Client Service on {host}:{port}")
    logger.info(f"Thermal zone path: {temp_reader.thermal_path}")

    try:
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service failed to start: {e}")
