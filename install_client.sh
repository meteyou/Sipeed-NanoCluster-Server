#!/bin/bash
# Sipeed NanoCluster Client Service Installation Script

set -e

# Configuration
SERVICE_NAME="sipeed-nanocluster-client"
SERVICE_USER="sipeed-nanocluster-client"
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON_VENV="${INSTALL_DIR}/venv"

echo "=== Sipeed NanoCluster Client Service Installation ==="
echo "Installing in directory: $INSTALL_DIR"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Check if we're in the correct directory (should contain src/client.py)
if [ ! -f "$INSTALL_DIR/src/client.py" ]; then
    echo "ERROR: client.py not found in src/ directory!"
    echo "Please make sure you're running this script from the Sipeed-NanoCluster-Server repository root."
    echo ""
    echo "Expected usage:"
    echo "  sudo ./install_client.sh"
    exit 1
fi

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed. Please install Python3 and run this script again."
    exit 1
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

# Create Python virtual environment
echo "Setting up Python virtual environment..."
sudo -u "$SERVICE_USER" python3 -m venv "$PYTHON_VENV"

# Install dependencies
echo "Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$PYTHON_VENV/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$PYTHON_VENV/bin/pip" install flask pyyaml gunicorn

# Create systemd service file
echo "Creating systemd service file..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Sipeed NanoCluster Client Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$PYTHON_VENV/bin
ExecStart=$PYTHON_VENV/bin/gunicorn --config client_config_gunicorn.py src.client:app
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
echo "Configuration file: $INSTALL_DIR/client_config.yaml"
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
echo "To test the API:"
echo "  curl http://localhost:5001/api/temperature"
