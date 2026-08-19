#!/bin/bash
# Deployment script for CVM
# Run this script on your CVM as azureuser

set -euo pipefail

REPO_URL="https://github.com/GarablueX/netsentry-gateway"
REPO_DIR="$HOME/netsentry-gateway"
BRANCH="ansible-and-nftables"

echo "=== NetSentry Gateway CVM Deployment ==="
echo "Repository: $REPO_URL"
echo "Branch: $BRANCH"
echo "Target directory: $REPO_DIR"
echo ""

# Update system
echo ">>> Updating package lists..."
sudo apt-get update

# Install required packages
echo ">>> Installing nftables, python3, git, and ansible..."
sudo apt-get install -y nftables python3 python3-pip git ansible

# Clone repository
echo ">>> Cloning repository..."
if [ -d "$REPO_DIR" ]; then
    echo "Repository already exists, pulling latest changes..."
    cd "$REPO_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
else
    git clone -b "$BRANCH" "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi

# Install Python dependencies
echo ">>> Installing Python dependencies..."
pip3 install pyyaml jinja2

# Copy CVM example vars if vars.yml doesn't exist or is default
echo ">>> Checking configuration..."
cd "$REPO_DIR"
if [ ! -f "config/vars.yml" ] || grep -q "wlx200db0220b9a" config/vars.yml; then
    echo ">>> Default vars.yml detected, copying CVM example..."
    cp config/vars.cvm.example.yml config/vars.yml
    echo "⚠ IMPORTANT: Edit config/vars.yml with your CVM's actual interface names!"
    echo "   Run: ip link show"
    echo "   Then update wan_interface, lan_interface, ap_interface in config/vars.yml"
    echo ""
    read -p "Press Enter after updating config/vars.yml to continue..."
fi

# Test template rendering using the validation script
echo ">>> Testing template rendering and validation..."
python3 validate-firewall.py

VALIDATION_RESULT=$?
if [ $VALIDATION_RESULT -ne 0 ]; then
    echo "Validation failed. Check output above."
    exit $VALIDATION_RESULT
fi

# Show the rendered ruleset
echo ""
echo "=== Rendered Firewall Rules ==="
cat firewall.rendered.nft

echo ""
echo "=== Deployment Complete ==="
echo "Rendered firewall saved to: $REPO_DIR/firewall.rendered.nft"
echo ""
echo "To apply the firewall rules:"
echo "  sudo nft -f $REPO_DIR/firewall.rendered.nft"
echo ""
echo "To verify applied rules:"
echo "  sudo nft list ruleset"
echo ""
echo "To make persistent across reboots:"
echo "  sudo cp $REPO_DIR/firewall.rendered.nft /etc/nftables.conf"
echo "  sudo systemctl enable nftables"
echo "  sudo systemctl start nftables"
