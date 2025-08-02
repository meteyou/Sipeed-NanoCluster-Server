#!/usr/bin/env python3
"""
Sipeed NanoCluster Client Service
A lightweight Flask service that provides temperature data via HTTP API.
This service is designed to run on each cluster node.
"""

from flask import Flask, jsonify
import os
import logging
from typing import Optional

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
DEFAULT_THERMAL_PATH = "/sys/class/thermal/thermal_zone0/temp"
DEFAULT_PORT = 5001
DEFAULT_HOST = "0.0.0.0"


class TemperatureReader:
    def __init__(self, thermal_path: str = DEFAULT_THERMAL_PATH):
        self.thermal_path = thermal_path

    def read_temperature(self) -> Optional[float]:
        """
        Read temperature from the thermal zone file.
        Returns temperature in Celsius or None if reading fails.
        """
        try:
            if not os.path.exists(self.thermal_path):
                logger.error(f"Thermal zone file not found: {self.thermal_path}")
                return None

            with open(self.thermal_path, 'r') as f:
                temp_millidegrees = f.read().strip()

            # Convert from millidegrees to degrees Celsius
            temp_celsius = float(temp_millidegrees) / 1000.0
            logger.debug(f"Read temperature: {temp_celsius}°C")
            return temp_celsius

        except FileNotFoundError:
            logger.error(f"Thermal zone file not found: {self.thermal_path}")
            return None
        except PermissionError:
            logger.error(f"Permission denied reading thermal zone file: {self.thermal_path}")
            return None
        except ValueError as e:
            logger.error(f"Invalid temperature data in {self.thermal_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading temperature: {e}")
            return None


# Initialize temperature reader
temp_reader = TemperatureReader()


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
    import argparse

    parser = argparse.ArgumentParser(description='Sipeed NanoCluster Client Service')
    parser.add_argument('--host', default=DEFAULT_HOST,
                       help=f'Host to bind to (default: {DEFAULT_HOST})')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                       help=f'Port to bind to (default: {DEFAULT_PORT})')
    parser.add_argument('--thermal-path', default=DEFAULT_THERMAL_PATH,
                       help=f'Path to thermal zone file (default: {DEFAULT_THERMAL_PATH})')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        app.config['DEBUG'] = True

    # Update thermal path if specified
    if args.thermal_path != DEFAULT_THERMAL_PATH:
        temp_reader.thermal_path = args.thermal_path
        logger.info(f"Using custom thermal path: {args.thermal_path}")

    logger.info(f"Starting Temperature Client Service on {args.host}:{args.port}")
    logger.info(f"Thermal zone path: {temp_reader.thermal_path}")

    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service failed to start: {e}")
