#!/bin/bash
set -e

PROJECT_DIR="/home/aegis/vault/projects/coa-dash"
SERVICE_FILE="$PROJECT_DIR/systemd/coa-dash.service"
SERVICE_TARGET="$HOME/.config/systemd/user/coa-dash.service"

echo "🦞 Installing COA-dash..."

# Create systemd user directory
mkdir -p "$HOME/.config/systemd/user"

# Copy service file
cp "$SERVICE_FILE" "$SERVICE_TARGET"
echo "✓ Service file installed"

# Reload systemd
systemctl --user daemon-reload
echo "✓ systemd reloaded"

# Enable and start service
systemctl --user enable coa-dash
systemctl --user start coa-dash
echo "✓ Service enabled and started"

# Check status
systemctl --user status coa-dash --no-pager

echo ""
echo "🦞 COA-dash installed successfully!"
echo "   Local: http://localhost:8890"
echo "   Tailscale: http://100.103.186.109:8890"
