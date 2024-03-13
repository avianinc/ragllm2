#!/bin/bash

# Update and upgrade
sudo apt update && apt upgrade

# Define your application directory
APP_DIR="/home/ubuntu/"

# Navigate to the application directory
cd "$APP_DIR"

# Check if the virtual environment folder exists; if not, create it
if [ ! -d "$APP_DIR/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate the virtual environment
source "$APP_DIR/venv/bin/activate"



# Install Python dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Deactivate the virtual environment
deactivate

# Create a systemd service file for the application
SERVICE_FILE="/etc/systemd/system/<your-app-name>.service"

echo "Creating systemd service file at $SERVICE_FILE"

# Use sudo to create or overwrite the systemd service file
sudo bash -c "cat > $SERVICE_FILE" << EOF
[Unit]
Description=Flask Application as Service
After=network.target

[Service]
User=<username>
Group=<usergroup>
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app

[Install]
WantedBy=multi-user.target
EOF

# Replace <username> and <usergroup> with your actual username and group

# Reload systemd to read the new service file
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable <your-app-name>

# Start the service
sudo systemctl start <your-app-name>

echo "Installation completed. The service is now running."
