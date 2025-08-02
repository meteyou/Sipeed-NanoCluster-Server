#!/bin/bash

# Sipeed NanoCluster Server Installation Script

set -e

# Configuration
SERVICE_NAME="sipeed-nanocluster-server"
SERVICE_USER="sipeed-nanocluster"
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON_VENV="${INSTALL_DIR}/venv"

echo "=== Sipeed NanoCluster Server Installation ==="
echo "Installing in directory: $INSTALL_DIR"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Check if we're in the correct directory (should contain src/server.py)
if [ ! -f "$INSTALL_DIR/src/server.py" ]; then
    echo "ERROR: server.py not found in src/ directory!"
    echo "Please make sure you're running this script from the sipeed-nanocluster-server repository root."
    echo ""
    echo "Expected usage:"
    echo "  git clone https://github.com/meteyou/sipeed-nanocluster-server.git"
    echo "  cd sipeed-nanocluster-server"
    echo "  sudo ./install_server.sh"
    exit 1
fi

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed. Please install Python3 and run this script again."
    exit 1
fi

# Install system dependencies (pigpio for GPIO control)
echo "Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    echo "Updating package lists..."
    apt-get update
    echo "Installing pigpio and python3-pigpio..."
    apt-get install -y pigpio python3-pigpio

    echo "Enabling and starting pigpio daemon..."
    systemctl enable pigpiod
    systemctl start pigpiod

    # Verify pigpio daemon is running
    if systemctl is-active --quiet pigpiod; then
        echo "pigpio daemon started successfully"
    else
        echo "WARNING: pigpio daemon failed to start. GPIO control may not work."
    fi
else
    echo "WARNING: apt-get not found. Please install pigpio manually:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install pigpio python3-pigpio"
    echo "  sudo systemctl enable pigpiod"
    echo "  sudo systemctl start pigpiod"
fi

# Stop and disable existing service if it exists
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Stopping existing service..."
    systemctl stop "$SERVICE_NAME"
fi
if systemctl is-enabled --quiet "$SERVICE_NAME"; then
    echo "Disabling existing service..."
    systemctl disable "$SERVICE_NAME"
fi
# Remove old service file if it exists
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
fi

# Create service user
echo "Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /bin/false --home-dir "$INSTALL_DIR" --create-home "$SERVICE_USER"
    echo "Created user: $SERVICE_USER"
else
    echo "User $SERVICE_USER already exists"
fi

# Set ownership of installation directory
echo "Setting up directory permissions..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Create or update Python virtual environment
if [ -d "$PYTHON_VENV" ]; then
    echo "Virtual environment already exists, updating..."
else
    echo "Creating Python virtual environment..."
    sudo -u "$SERVICE_USER" python3 -m venv "$PYTHON_VENV"
fi

# Install/update dependencies
echo "Installing/updating Python dependencies..."
sudo -u "$SERVICE_USER" "$PYTHON_VENV/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$PYTHON_VENV/bin/pip" install -r requirements.txt

# Copy example configuration file if it doesn't exist
if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
    echo "Creating default configuration file..."
    sudo -u "$SERVICE_USER" cp "$INSTALL_DIR/config.yaml.example" "$INSTALL_DIR/config.yaml"
    echo "Please edit $INSTALL_DIR/config.yaml to configure the server."
fi

# Set ownership of configuration files
echo "Setting ownership of configuration files..."
chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/config.yaml"

# Create systemd service file
echo "Creating systemd service file..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Sipeed NanoCluster Server Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$PYTHON_VENV/bin
ExecStart=$PYTHON_VENV/bin/gunicorn --config server_gunicorn_config.py src.server:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
echo "Enabling systemd service..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "=== Installation Complete ==="
echo "Service installed as: $SERVICE_NAME"
echo "Installation directory: $INSTALL_DIR"
echo "Configuration file: $INSTALL_DIR/config.yaml"
echo ""
echo "To start the service:"
echo "  sudo systemctl start $SERVICE_NAME"
echo ""
echo "To check service status:"
echo "  sudo systemctl status $SERVICE_NAME"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "To test the web interface:"
echo "  Open browser: http://localhost:5000"
