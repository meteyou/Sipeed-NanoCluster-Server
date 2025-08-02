# Auf dem Raspberry Pi
sudo apt-get update
sudo apt-get install pigpio python3-pigpio

# Starte den pigpio Daemon
sudo systemctl enable pigpiod
sudo systemctl start pigpiod




curl -LsSf https://astral.sh/uv/install.sh | sh