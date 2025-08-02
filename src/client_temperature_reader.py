
import os
from typing import Optional

class ClientTemperatureReader:
    def __init__(self, logger, thermal_path: str = None):
        self.logger = logger
        self.thermal_path = thermal_path

    def read_temperature(self) -> Optional[float]:
        """
        Read temperature from the thermal zone file.
        Returns temperature in Celsius or None if reading fails.
        """
        try:
            if not os.path.exists(self.thermal_path):
                self.logger.error(f"Thermal zone file not found: {self.thermal_path}")
                return None

            with open(self.thermal_path, 'r') as f:
                temp_millidegrees = f.read().strip()

            # Convert from millidegrees to degrees Celsius
            temp_celsius = float(temp_millidegrees) / 1000.0
            self.logger.debug(f"Read temperature: {temp_celsius}°C")
            return temp_celsius

        except FileNotFoundError:
            self.logger.error(f"Thermal zone file not found: {self.thermal_path}")
            return None
        except PermissionError:
            self.logger.error(f"Permission denied reading thermal zone file: {self.thermal_path}")
            return None
        except ValueError as e:
            self.logger.error(f"Invalid temperature data in {self.thermal_path}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error reading temperature: {e}")
            return None