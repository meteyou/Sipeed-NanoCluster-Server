#!/bin/bash

# Sipeed NanoCluster Server Installation Script

set -e

# Configuration
SERVICE_NAME="sipeed-nanocluster-server"
SERVICE_USER="sipeed-nanocluster"
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PIGPIOD_SERVICE_FILE="/etc/systemd/system/pigpiod.service"
PYTHON_VENV="${INSTALL_DIR}/venv"

apt_package_available() {
    local candidate
    candidate="$(apt-cache policy "$1" 2>/dev/null | awk '/Candidate:/ {print $2}')"
    [ -n "$candidate" ] && [ "$candidate" != "(none)" ]
}

install_pigpio_from_source() {
    local tmp_dir
    tmp_dir="$(mktemp -d)"

    echo "pigpio package not available via apt. Building pigpio from source..."
    apt-get install -y build-essential curl tar

    curl -L https://github.com/joan2937/pigpio/archive/refs/heads/master.tar.gz -o "$tmp_dir/pigpio.tar.gz"
    tar -xzf "$tmp_dir/pigpio.tar.gz" -C "$tmp_dir"

    pushd "$tmp_dir/pigpio-master" >/dev/null
    make

    install -m 0755 -d /usr/local/include /usr/local/lib /usr/local/bin
    install -m 0644 pigpio.h pigpiod_if.h pigpiod_if2.h /usr/local/include/
    install -m 0755 libpigpio.so.1 libpigpiod_if.so.1 libpigpiod_if2.so.1 /usr/local/lib/
    ln -sf /usr/local/lib/libpigpio.so.1 /usr/local/lib/libpigpio.so
    ln -sf /usr/local/lib/libpigpiod_if.so.1 /usr/local/lib/libpigpiod_if.so
    ln -sf /usr/local/lib/libpigpiod_if2.so.1 /usr/local/lib/libpigpiod_if2.so
    install -m 0755 pig2vcd pigpiod pigs /usr/local/bin/
    popd >/dev/null

    ldconfig

    if [ ! -f "$PIGPIOD_SERVICE_FILE" ]; then
        cat > "$PIGPIOD_SERVICE_FILE" << 'EOF'
[Unit]
Description=Pigpio daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/pigpiod -g
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    fi

    systemctl daemon-reload
    rm -rf "$tmp_dir"
}

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

    if apt_package_available pigpio; then
        echo "Installing pigpio and python3-pigpio from apt..."
        apt-get install -y pigpio python3-pigpio
    else
        echo "pigpio apt package not available (common on Debian Trixie)."

        if apt_package_available python3-pigpio; then
            echo "Installing python3-pigpio client package from apt..."
            apt-get install -y python3-pigpio
        else
            echo "python3-pigpio apt package not available. Will use the Python package from requirements.txt."
        fi

        install_pigpio_from_source
    fi

    if systemctl list-unit-files | grep -q '^pigpiod.service'; then
        echo "Enabling and starting pigpio daemon..."
        systemctl enable pigpiod
        systemctl restart pigpiod

        # Verify pigpio daemon is running
        if systemctl is-active --quiet pigpiod; then
            echo "pigpio daemon started successfully"
        else
            echo "WARNING: pigpio daemon failed to start. GPIO control may not work."
        fi
    else
        echo "WARNING: pigpiod.service not found. GPIO control may not work."
    fi
else
    echo "WARNING: apt-get not found. Please install pigpio manually."
    echo "On Debian Trixie you likely need to build pigpio from source:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y build-essential curl tar python3-pigpio"
    echo "  tmpdir=\$(mktemp -d)"
    echo "  curl -L https://github.com/joan2937/pigpio/archive/refs/heads/master.tar.gz -o \$tmpdir/pigpio.tar.gz"
    echo "  tar -xzf \$tmpdir/pigpio.tar.gz -C \$tmpdir"
    echo "  cd \$tmpdir/pigpio-master && make"
    echo "  sudo install -m 0755 pigpiod pigs /usr/local/bin/"
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
ExecStart=$PYTHON_VENV/bin/python3 $INSTALL_DIR/src/server.py
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
