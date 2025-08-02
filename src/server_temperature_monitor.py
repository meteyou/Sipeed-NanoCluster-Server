import threading
import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from server_config_manager import ConfigManager
import pigpio

logger = logging.getLogger(__name__)


class TemperatureMonitor:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.temperature_data = {}
        self.is_running = False
        self.monitor_thread = None
        self._stop_event = threading.Event()

        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("No connection to pigpio daemon. Make sure it is running.")

        self.gpio_pin = self.config_manager.get_fan_config().get('gpio_pin', 13)

    def start_monitoring(self):
        """Starts temperature monitoring in the background"""
        if self.is_running:
            logger.warning("Temperature monitoring is already running")
            return

        self.is_running = True
        self._stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Temperature monitoring started")

    def stop_monitoring(self):
        """Stops temperature monitoring"""
        if not self.is_running:
            return

        self.is_running = False
        self._stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Temperature monitoring stopped")

    def _monitor_loop(self):
        """Main loop for temperature monitoring"""
        config = self.config_manager.get_temperature_monitoring_config()
        interval = config.get('interval_seconds', 30)

        while self.is_running and not self._stop_event.is_set():
            try:
                self._poll_all_nodes()
            except Exception as e:
                logger.error(f"Error during temperature polling: {e}")

            # Wait for the configured interval or until stop event is set
            self._stop_event.wait(timeout=interval)
            self._set_fan_speed_based_on_temperature()

    def _poll_all_nodes(self):
        """Polls all active nodes for their temperature"""
        enabled_nodes = self.config_manager.get_enabled_nodes()
        config = self.config_manager.get_temperature_monitoring_config()
        endpoint = config.get('endpoint', '/api/temperature')
        timeout = config.get('timeout', 5)

        for node in enabled_nodes:
            try:
                temperature = self._poll_node_temperature(node, endpoint, timeout)
                if temperature is not None:
                    self._store_temperature_data(node, temperature)
            except Exception as e:
                logger.error(f"Failed to poll temperature from node {node['name']}: {e}")

    def _poll_node_temperature(self, node: Dict[str, Any], endpoint: str, timeout: int) -> Optional[float]:
        """Polls a single node for its temperature"""
        url = f"http://{node['ip']}:{node['port']}{endpoint}"

        try:
            logger.debug(f"Polling temperature from {node['name']} at {url}")
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()

            data = response.json()
            temperature = data.get('temperature')

            if temperature is not None:
                logger.debug(f"Node {node['name']} temperature: {temperature}°C")
                return float(temperature)
            else:
                logger.warning(f"No temperature data in response from {node['name']}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout polling temperature from node {node['name']}")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error polling temperature from node {node['name']}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error polling temperature from node {node['name']}: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid response format from node {node['name']}: {e}")
            return None

    def _store_temperature_data(self, node: Dict[str, Any], temperature: float):
        """Stores temperature data for a node"""
        node_name = node['name']
        timestamp = datetime.now().isoformat()

        if node_name not in self.temperature_data:
            self.temperature_data[node_name] = []

        # Add current temperature
        self.temperature_data[node_name].append({
            'timestamp': timestamp,
            'temperature': temperature,
            'slot': node['slot']
        })

        # Keep only the last 100 entries (to save memory)
        if len(self.temperature_data[node_name]) > 100:
            self.temperature_data[node_name] = self.temperature_data[node_name][-100:]

        logger.info(f"Stored temperature data for {node_name}: {temperature}°C")

    def _set_fan_speed_based_on_temperature(self):
        """Sets the fan speed based on the current temperature data"""
        fan_config = self.config_manager.get_fan_config()
        if not fan_config:
            logger.warning("Fan configuration not found")
            return

        min_temp = fan_config.get('min_temp', 40)
        max_temp = fan_config.get('max_temp', 70)
        min_speed = fan_config.get('min_speed', 30)
        max_speed = fan_config.get('max_speed', 100)

        current_max_temp = float("-inf")

        for node_name, data_list in self.temperature_data.items():
            if not data_list:
                continue

            latest_entry = data_list[-1]
            temperature = latest_entry['temperature']

            if temperature > current_max_temp:
                current_max_temp = temperature

        # Calculate fan speed based on temperature
        if current_max_temp < min_temp:
            speed = min_speed
        elif current_max_temp > max_temp:
            speed = max_speed
        else:
            # Linear interpolation between min and max
            speed = int(min_speed + (max_speed - min_speed) * (current_max_temp - min_temp) / (max_temp - min_temp))

        # Here you would set the actual fan speed using GPIO or other methods
        logger.info(f"Setting fan speed to {speed}% based on temperature {current_max_temp}°C")
        duty_cycle = int(speed * 10000)  # 0-1000000
        self.pi.hardware_PWM(self.gpio_pin, 50, duty_cycle)

    def get_latest_temperatures(self) -> Dict[str, Any]:
        """Returns the latest temperature data of all nodes"""
        latest_data = {}

        for node_name, data_list in self.temperature_data.items():
            if data_list:
                latest_entry = data_list[-1]
                latest_data[node_name] = {
                    'temperature': latest_entry['temperature'],
                    'timestamp': latest_entry['timestamp'],
                    'slot': latest_entry['slot']
                }

        return latest_data

    def get_node_temperature_history(self, node_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the temperature history of a specific node"""
        if node_name not in self.temperature_data:
            return []

        return self.temperature_data[node_name][-limit:]

    def get_all_temperature_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns all stored temperature data"""
        return self.temperature_data.copy()
